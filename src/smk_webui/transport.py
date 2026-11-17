"""Six 64-byte HID interrupt-OUT reports per frame, with timed overlapped writes."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
from .hid import WindowsHID
import time
from .onboard import Control

ROOT=Path(__file__).resolve().parent
PRODUCT='SMK X77 Fast v1'


def frame_packets(pixels, sequence):
    if not 0<=sequence<=255 or len(pixels)!=108 or any(len(p)!=3 or any(type(v)!=int or not 0<=v<=255 for v in p) for p in pixels):
        raise ValueError('Expected 108 RGB byte triples and a byte sequence number')
    for chunk in range(6):
        cells=pixels[chunk*19:(chunk+1)*19]
        data=bytes((10,70,1,sequence,chunk,len(cells),0))+bytes(v for rgb in cells for v in rgb)
        yield data.ljust(64,b'\0')


def release_packet():
    return bytes((10,70,1,0,0,0,1))+bytes(57)


class Overlapped(c.Structure):
    _fields_=[('Internal',c.c_size_t),('InternalHigh',c.c_size_t),
              ('Offset',w.DWORD),('OffsetHigh',w.DWORD),('hEvent',w.HANDLE)]


class Transport:
    def __init__(self):
        self.api=WindowsHID(PRODUCT,64)
        self.kernel=self.api.kernel
        definitions=[
            ('CreateEventW',w.HANDLE,[w.LPVOID,w.BOOL,w.BOOL,w.LPCWSTR]),
            ('ResetEvent',w.BOOL,[w.HANDLE]),
            ('WaitForSingleObject',w.DWORD,[w.HANDLE,w.DWORD]),
            ('WriteFile',w.BOOL,[w.HANDLE,w.LPVOID,w.DWORD,c.POINTER(w.DWORD),c.POINTER(Overlapped)]),
            ('GetOverlappedResult',w.BOOL,[w.HANDLE,c.POINTER(Overlapped),c.POINTER(w.DWORD),w.BOOL]),
            ('CancelIoEx',w.BOOL,[w.HANDLE,c.POINTER(Overlapped)]),
        ]
        for name,result,args in definitions:
            fn=getattr(self.kernel,name);fn.restype=result;fn.argtypes=args
        paths=self.api.devices()
        if len(paths)!=1: raise RuntimeError('No single available SMK X77 Fast v1 device. Check the connection and close other lighting apps.')
        # Deny other readers/writers on this vendor lighting collection.
        # Keyboard input uses separate HID collections and remains available.
        self.handle=self.kernel.CreateFileW(paths[0],0x40000000,0,None,3,0x40000000,None)
        if self.handle==c.c_void_p(-1).value:
            error=c.get_last_error()
            if error in (5,32):raise RuntimeError('Lighting device is in use. Close the other SMK app or lighting bridge.')
            raise c.WinError(error)
        self.event=None
        try:
            if not self.api.matches(self.handle): raise RuntimeError('Device identity changed')
            self.event=self.kernel.CreateEventW(None,True,False,None)
            if not self.event: raise c.WinError(c.get_last_error())
        except BaseException:
            self.kernel.CloseHandle(self.handle)
            raise
        self.sequence=0
        self.frames=0
        self.transfer_seconds=0
        self.api.hid.HidD_GetFeature.argtypes=[w.HANDLE,w.LPVOID,w.ULONG]
        self.api.hid.HidD_GetFeature.restype=c.c_ubyte
        try:self.control=Control(self.get_feature,self.set_feature)
        except (OSError,ValueError):self.control=None

    def get_feature(self,report):
        data=c.create_string_buffer(bytes((report,))+bytes(7),8)
        if not self.api.hid.HidD_GetFeature(self.handle,data,8):raise c.WinError(c.get_last_error())
        return data.raw

    def set_feature(self,packet):
        data=c.create_string_buffer(packet,8)
        if not self.api.hid.HidD_SetFeature(self.handle,data,8):raise c.WinError(c.get_last_error())

    def write(self,packet):
        if len(packet)!=64: raise ValueError('Output reports must be 64 bytes')
        data=c.create_string_buffer(packet,64)
        pending=Overlapped();pending.hEvent=self.event
        count=w.DWORD()
        if not self.kernel.ResetEvent(self.event): raise c.WinError(c.get_last_error())
        if not self.kernel.WriteFile(self.handle,data,64,None,c.byref(pending)):
            error=c.get_last_error()
            if error!=997: raise c.WinError(error)
            wait=self.kernel.WaitForSingleObject(self.event,1000)
            if wait!=0:
                self.kernel.CancelIoEx(self.handle,c.byref(pending))
                # Keep the OVERLAPPED and data alive until cancellation completes.
                self.kernel.GetOverlappedResult(self.handle,c.byref(pending),c.byref(count),True)
                raise TimeoutError('Keyboard output did not complete within one second; streaming stopped')
        if not self.kernel.GetOverlappedResult(self.handle,c.byref(pending),c.byref(count),False):
            raise c.WinError(c.get_last_error())
        if count.value!=64: raise OSError(f'Short HID output write: {count.value}/64')

    def send(self,pixels):
        if pixels is None:
            self.write(release_packet())
            return
        start=time.perf_counter()
        for packet in frame_packets(pixels,self.sequence): self.write(packet)
        self.sequence=(self.sequence+1)&255
        self.frames+=1
        self.transfer_seconds+=time.perf_counter()-start

    def close(self):
        try:
            self.send(None)
        finally:
            self.kernel.CloseHandle(self.event)
            self.kernel.CloseHandle(self.handle)
