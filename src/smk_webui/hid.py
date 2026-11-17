"""Windows HID enumeration and device matching."""
import ctypes as c
from ctypes import wintypes as w

PRODUCT = 'SMK X77 Fast v1'


class GUID(c.Structure):
    _fields_ = [('a', w.DWORD), ('b', w.WORD), ('d', w.WORD), ('e', c.c_ubyte * 8)]


class Interface(c.Structure):
    _fields_ = [('size', w.DWORD), ('guid', GUID), ('flags', w.DWORD), ('reserved', c.c_size_t)]


class Attributes(c.Structure):
    _fields_ = [('size', w.DWORD), ('vid', w.WORD), ('pid', w.WORD), ('version', w.WORD)]


class Caps(c.Structure):
    _fields_ = [('usage', w.WORD), ('page', w.WORD), ('input', w.WORD),
                ('output', w.WORD), ('feature', w.WORD), ('reserved', w.WORD * 17),
                ('rest', w.WORD * 10)]


class WindowsHID:
    def __init__(self, product=PRODUCT, output_length=None):
        self.product = product
        self.output_length = output_length
        self.hid = c.WinDLL('hid', use_last_error=True)
        self.setup = c.WinDLL('setupapi', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        definitions = [
            (self.hid, 'HidD_GetHidGuid', None, [c.POINTER(GUID)]),
            (self.hid, 'HidD_GetAttributes', c.c_ubyte, [w.HANDLE, c.POINTER(Attributes)]),
            (self.hid, 'HidD_GetProductString', c.c_ubyte, [w.HANDLE, w.LPVOID, w.ULONG]),
            (self.hid, 'HidD_GetPreparsedData', c.c_ubyte, [w.HANDLE, c.POINTER(w.LPVOID)]),
            (self.hid, 'HidD_FreePreparsedData', c.c_ubyte, [w.LPVOID]),
            (self.hid, 'HidP_GetCaps', w.LONG, [w.LPVOID, c.POINTER(Caps)]),
            (self.hid, 'HidD_SetFeature', c.c_ubyte, [w.HANDLE, w.LPVOID, w.ULONG]),
            (self.setup, 'SetupDiGetClassDevsW', w.HANDLE, [c.POINTER(GUID), w.LPCWSTR, w.HWND, w.DWORD]),
            (self.setup, 'SetupDiEnumDeviceInterfaces', w.BOOL, [w.HANDLE, w.LPVOID, c.POINTER(GUID), w.DWORD, c.POINTER(Interface)]),
            (self.setup, 'SetupDiGetDeviceInterfaceDetailW', w.BOOL, [w.HANDLE, c.POINTER(Interface), w.LPVOID, w.DWORD, c.POINTER(w.DWORD), w.LPVOID]),
            (self.setup, 'SetupDiDestroyDeviceInfoList', w.BOOL, [w.HANDLE]),
            (self.kernel, 'CreateFileW', w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]),
            (self.kernel, 'CloseHandle', w.BOOL, [w.HANDLE]),
        ]
        for dll, name, result, args in definitions:
            fn = getattr(dll, name)
            fn.restype, fn.argtypes = result, args

    def open(self, path):
        handle = self.kernel.CreateFileW(path, 0, 3, None, 3, 0, None)
        if handle == c.c_void_p(-1).value:
            raise c.WinError(c.get_last_error())
        return handle

    def matches(self, handle):
        attributes = Attributes(c.sizeof(Attributes))
        if not self.hid.HidD_GetAttributes(handle, c.byref(attributes)):
            return False
        if (attributes.vid, attributes.pid) != (0x258a, 0x0016):
            return False
        product = c.create_unicode_buffer(128)
        if not self.hid.HidD_GetProductString(handle, product, c.sizeof(product)) or product.value != self.product:
            return False
        data = w.LPVOID()
        if not self.hid.HidD_GetPreparsedData(handle, c.byref(data)):
            return False
        try:
            caps = Caps()
            return (self.hid.HidP_GetCaps(data, c.byref(caps)) == 0x110000
                    and (caps.page, caps.usage, caps.feature) == (0xff32, 1, 8)
                    and (self.output_length is None or caps.output == self.output_length))
        finally:
            self.hid.HidD_FreePreparsedData(data)

    def devices(self):
        guid = GUID()
        self.hid.HidD_GetHidGuid(c.byref(guid))
        info = self.setup.SetupDiGetClassDevsW(c.byref(guid), None, None, 0x12)
        if info == c.c_void_p(-1).value:
            raise c.WinError(c.get_last_error())
        found = []
        try:
            index = 0
            while True:
                interface = Interface()
                interface.size = c.sizeof(interface)
                if not self.setup.SetupDiEnumDeviceInterfaces(info, None, c.byref(guid), index, c.byref(interface)):
                    if c.get_last_error() == 259:
                        break
                    raise c.WinError(c.get_last_error())
                index += 1
                needed = w.DWORD()
                self.setup.SetupDiGetDeviceInterfaceDetailW(info, c.byref(interface), None, 0, c.byref(needed), None)
                if needed.value < 8:
                    continue
                detail = c.create_string_buffer(needed.value)
                c.cast(detail, c.POINTER(w.DWORD))[0] = 8 if c.sizeof(c.c_void_p) == 8 else 6
                if not self.setup.SetupDiGetDeviceInterfaceDetailW(info, c.byref(interface), detail, needed.value, None, None):
                    continue
                path = c.wstring_at(c.addressof(detail) + 4)
                if 'vid_258a&pid_0016' not in path.lower():
                    continue
                try:
                    handle = self.open(path)
                except OSError:
                    continue
                try:
                    if self.matches(handle):
                        found.append(path)
                finally:
                    self.kernel.CloseHandle(handle)
        finally:
            self.setup.SetupDiDestroyDeviceInfoList(info)
        return found
