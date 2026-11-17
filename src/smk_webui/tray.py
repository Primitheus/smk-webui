"""Windows notification-area controls; no GUI toolkit dependency."""
import ctypes as c
from ctypes import wintypes as w
import webbrowser
from pathlib import Path
from . import startup


def run_tray(app,url):
    user=c.WinDLL('user32',use_last_error=True)
    shell=c.WinDLL('shell32',use_last_error=True)
    kernel=c.WinDLL('kernel32',use_last_error=True)
    callback=c.WINFUNCTYPE(c.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
    class WindowClass(c.Structure):
        _fields_=[('style',w.UINT),('proc',callback),('extra',c.c_int),('window_extra',c.c_int),('instance',w.HINSTANCE),('icon',w.HICON),('cursor',w.HANDLE),('background',w.HBRUSH),('menu',w.LPCWSTR),('name',w.LPCWSTR)]
    class Notify(c.Structure):
        _fields_=[('size',w.DWORD),('window',w.HWND),('id',w.UINT),('flags',w.UINT),('message',w.UINT),('icon',w.HICON),('tip',w.WCHAR*128),('state',w.DWORD),('mask',w.DWORD),('info',w.WCHAR*256),('version',w.UINT),('title',w.WCHAR*64),('info_flags',w.DWORD),('guid',c.c_byte*16),('balloon_icon',w.HICON)]
    def declare(lib,name,args,result):
        fn=getattr(lib,name);fn.argtypes=args;fn.restype=result;return fn
    declare(kernel,'GetModuleHandleW',[w.LPCWSTR],w.HMODULE)
    declare(user,'DefWindowProcW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM],c.c_ssize_t)
    declare(user,'RegisterClassW',[c.POINTER(WindowClass)],w.ATOM)
    declare(user,'CreateWindowExW',[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p],w.HWND)
    declare(user,'LoadIconW',[w.HINSTANCE,c.c_void_p],w.HICON)
    declare(user,'LoadImageW',[w.HINSTANCE,w.LPCWSTR,w.UINT,c.c_int,c.c_int,w.UINT],w.HANDLE)
    declare(user,'DestroyIcon',[w.HICON],w.BOOL)
    declare(user,'CreatePopupMenu',[],w.HMENU)
    declare(user,'AppendMenuW',[w.HMENU,w.UINT,c.c_size_t,w.LPCWSTR],w.BOOL)
    declare(user,'TrackPopupMenu',[w.HMENU,w.UINT,c.c_int,c.c_int,c.c_int,w.HWND,c.c_void_p],w.UINT)
    declare(user,'DestroyMenu',[w.HMENU],w.BOOL)
    declare(user,'SetForegroundWindow',[w.HWND],w.BOOL)
    declare(user,'DestroyWindow',[w.HWND],w.BOOL)
    declare(user,'SetTimer',[w.HWND,c.c_size_t,w.UINT,c.c_void_p],c.c_size_t)
    declare(user,'GetMessageW',[c.POINTER(w.MSG),w.HWND,w.UINT,w.UINT],w.BOOL)
    declare(user,'DispatchMessageW',[c.POINTER(w.MSG)],c.c_ssize_t)
    declare(shell,'Shell_NotifyIconW',[w.DWORD,c.POINTER(Notify)],w.BOOL)
    @callback
    def procedure(hwnd,message,wp,lp):
        if message==0x8001:
            if lp==0x202:webbrowser.open(url)
            elif lp==0x205:
                menu=user.CreatePopupMenu()
                auto=startup.status()
                for identifier,label in [(1,'Open SMK WebUI'),(2,'Use Onboard Lighting'),(4,'Disable Auto Start' if auto['enabled'] else 'Enable Auto Start'),(3,'Quit')]:user.AppendMenuW(menu,1 if identifier==4 and not auto['available'] else 0,identifier,label)
                point=w.POINT();user.GetCursorPos(c.byref(point));user.SetForegroundWindow(hwnd)
                choice=user.TrackPopupMenu(menu,0x100|2,point.x,point.y,0,hwnd,None);user.DestroyMenu(menu)
                if choice==1:webbrowser.open(url)
                elif choice==2:app.patch({'mode':3})
                elif choice==3:app.stop.set()
                elif choice==4:
                    try:startup.set_enabled(not auto['enabled'])
                    except (OSError,ValueError) as exc:app.log.logger.error('Startup setting failed: %s',exc)
            return 0
        if message==0x113 and app.stop.is_set():user.DestroyWindow(hwnd);return 0
        if message==2:user.PostQuitMessage(0);return 0
        return user.DefWindowProcW(hwnd,message,wp,lp)
    instance=kernel.GetModuleHandleW(None)
    wc=WindowClass();wc.proc=procedure;wc.instance=instance;wc.name='SMKWebUITray'
    if not user.RegisterClassW(c.byref(wc)):raise c.WinError(c.get_last_error())
    hwnd=user.CreateWindowExW(0,wc.name,'SMK WebUI',0,0,0,0,0,None,None,instance,None)
    if not hwnd:raise c.WinError(c.get_last_error())
    icon=user.LoadImageW(None,str(Path(__file__).with_name('web')/'icon.ico'),1,0,0,0x10|0x40)
    note=Notify();note.size=c.sizeof(note);note.window=hwnd;note.id=1;note.flags=7;note.message=0x8001;note.icon=icon or user.LoadIconW(None,32512);note.tip='SMK WebUI — click to open'
    if not shell.Shell_NotifyIconW(0,c.byref(note)):raise RuntimeError('Could not create tray icon')
    user.SetTimer(hwnd,1,250,None)
    try:
        message=w.MSG()
        while user.GetMessageW(c.byref(message),None,0,0)>0:
            user.TranslateMessage(c.byref(message));user.DispatchMessageW(c.byref(message))
    finally:
        shell.Shell_NotifyIconW(2,c.byref(note))
        if icon:user.DestroyIcon(icon)
