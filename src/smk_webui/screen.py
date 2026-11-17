"""Local, on-demand desktop colour sampling. No images are saved or served."""
import ctypes as c
from ctypes import wintypes as w
import threading
import time

WIDTH,HEIGHT=72,24

def signature(layer):return (layer.get('screen_monitor',''),tuple(layer.get('screen_region',[0,0,100,100])))

def requests(state):
    with state.lock:
        if state.mode!=8:return set()
        solo=state.solo_index if time.monotonic()<state.solo_until else None
        return {signature(p) for i,p in enumerate(state.studio['layers']) if p['type']=='Screen Colours' and (i==solo if solo is not None else p['enabled'])}

def region_bounds(monitor,region):
    x,y,width,height=region
    left,top,right,bottom=monitor['bounds'];mw=right-left;mh=bottom-top
    return (left+round(mw*x/100),top+round(mh*y/100),max(1,round(mw*(x+width)/100)-round(mw*x/100)),max(1,round(mh*(y+height)/100)-round(mh*y/100)))

def reduce_bgra(data):
    if len(data)!=WIDTH*HEIGHT*4:raise ValueError('Invalid screen sample size')
    result=[]
    for row in range(6):
        for col in range(18):
            totals=[0,0,0]
            for y in range(row*4,row*4+4):
                for x in range(col*4,col*4+4):
                    at=(y*WIDTH+x)*4
                    for channel in range(3):totals[channel]+=data[at+2-channel]
            result.append(tuple(round(v/16) for v in totals))
    return result

class MonitorInfo(c.Structure):
    _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD),('device',w.WCHAR*32)]
class BitmapInfo(c.Structure):
    _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),('xppm',w.LONG),('yppm',w.LONG),('used',w.DWORD),('important',w.DWORD)]

class Desktop:
    def __init__(self):
        self.user=c.WinDLL('user32',use_last_error=True);self.gdi=c.WinDLL('gdi32',use_last_error=True)
        self.callback=c.WINFUNCTYPE(w.BOOL,w.HANDLE,w.HDC,c.POINTER(w.RECT),w.LPARAM)
        functions=[(self.user,'EnumDisplayMonitors',w.BOOL,[w.HDC,c.POINTER(w.RECT),self.callback,w.LPARAM]),
          (self.user,'GetMonitorInfoW',w.BOOL,[w.HANDLE,c.c_void_p]),(self.user,'GetDC',w.HDC,[w.HWND]),(self.user,'ReleaseDC',c.c_int,[w.HWND,w.HDC]),
          (self.gdi,'CreateCompatibleDC',w.HDC,[w.HDC]),(self.gdi,'DeleteDC',w.BOOL,[w.HDC]),(self.gdi,'DeleteObject',w.BOOL,[w.HANDLE]),
          (self.gdi,'CreateDIBSection',w.HBITMAP,[w.HDC,c.c_void_p,w.UINT,c.POINTER(c.c_void_p),w.HANDLE,w.DWORD]),
          (self.gdi,'SelectObject',w.HANDLE,[w.HDC,w.HANDLE]),(self.gdi,'SetStretchBltMode',c.c_int,[w.HDC,c.c_int]),
          (self.gdi,'StretchBlt',w.BOOL,[w.HDC,c.c_int,c.c_int,c.c_int,c.c_int,w.HDC,c.c_int,c.c_int,c.c_int,c.c_int,w.DWORD]),
          (self.gdi,'SetBrushOrgEx',w.BOOL,[w.HDC,c.c_int,c.c_int,c.c_void_p]),(self.gdi,'GdiFlush',w.BOOL,[])]
        for lib,name,result,args in functions:fn=getattr(lib,name);fn.restype=result;fn.argtypes=args
        self.dpi=getattr(self.user,'SetThreadDpiAwarenessContext',None)
        if self.dpi:self.dpi.argtypes=[c.c_void_p];self.dpi.restype=c.c_void_p
        self.source=self.memory=self.bitmap=self.previous=None;self.bits=c.c_void_p()
    def monitors(self):
        old=self.dpi(c.c_void_p(-4)) if self.dpi else None
        result=[]
        def visit(handle,dc,rect,data):
            info=MonitorInfo();info.size=c.sizeof(info)
            if self.user.GetMonitorInfoW(handle,c.byref(info)):
                r=info.monitor;result.append(dict(id=info.device,name=info.device.replace('\\\\.\\',''),primary=bool(info.flags&1),bounds=[r.left,r.top,r.right,r.bottom],width=r.right-r.left,height=r.bottom-r.top))
            return True
        try:
            if not self.user.EnumDisplayMonitors(None,None,self.callback(visit),0):raise OSError('Display enumeration failed')
            return sorted(result,key=lambda m:(not m['primary'],m['id']))
        finally:
            if old:self.dpi(old)
    def sample(self,bounds):
        old=self.dpi(c.c_void_p(-4)) if self.dpi else None
        try:
            if not self.source:
                self.source=self.user.GetDC(None)
                if not self.source:raise OSError('Desktop capture unavailable')
                self.memory=self.gdi.CreateCompatibleDC(self.source)
                if not self.memory:raise OSError('Could not create screen sampler')
                info=BitmapInfo();info.size=c.sizeof(info);info.width=WIDTH;info.height=-HEIGHT;info.planes=1;info.bits=32
                self.bitmap=self.gdi.CreateDIBSection(self.source,c.byref(info),0,c.byref(self.bits),None,0)
                if not self.bitmap or not self.bits.value:raise OSError('Could not allocate screen sampler')
                self.previous=self.gdi.SelectObject(self.memory,self.bitmap)
                if not self.previous or self.previous==c.c_void_p(-1).value:raise OSError('Could not select screen sampler')
                self.gdi.SetStretchBltMode(self.memory,4);self.gdi.SetBrushOrgEx(self.memory,0,0,None)
            x,y,width,height=bounds
            if not self.gdi.StretchBlt(self.memory,0,0,WIDTH,HEIGHT,self.source,x,y,width,height,0x40cc0020):raise OSError('Screen capture unavailable on this desktop')
            if not self.gdi.GdiFlush():raise OSError('Could not finish screen sampling')
            return reduce_bgra(c.string_at(self.bits,WIDTH*HEIGHT*4))
        finally:
            if old:self.dpi(old)
    def close(self):
        if self.memory and self.previous:self.gdi.SelectObject(self.memory,self.previous)
        if self.bitmap:self.gdi.DeleteObject(self.bitmap)
        if self.memory:self.gdi.DeleteDC(self.memory)
        if self.source:self.user.ReleaseDC(None,self.source)
        self.source=self.memory=self.bitmap=self.previous=None

def monitors():
    desktop=Desktop()
    try:return desktop.monitors()
    finally:desktop.close()

class ScreenCapture:
    def __init__(self,state,stop,logger):self.state=state;self.stop=stop;self.logger=logger;self.thread=None
    def start(self):
        self.thread=threading.Thread(target=self.run,name='screen-colours',daemon=True);self.thread.start()
    def run(self):
        desktop=None;retry=0;last_error=None
        try:
            while not self.stop.wait(.1):
                needed=requests(self.state)
                if not needed:
                    if desktop:desktop.close();desktop=None
                    with self.state.lock:self.state.screen_frames={};self.state.screen_status='Idle'
                    retry=0;continue
                if time.monotonic()<retry:continue
                try:
                    if desktop is None:desktop=Desktop()
                    displays=desktop.monitors();frames={};missing=False
                    for monitor_id,region in needed:
                        monitor=next((m for m in displays if m['id']==monitor_id or not monitor_id and m['primary']),None)
                        if monitor is None:missing=True;continue
                        pixels=desktop.sample(region_bounds(monitor,region));frames[(monitor_id,region)]=(pixels,time.monotonic())
                    with self.state.lock:self.state.screen_frames=frames;self.state.screen_status='Display Unavailable' if missing else 'Capturing'
                    last_error=None
                except (OSError,AttributeError) as exc:
                    if desktop:desktop.close();desktop=None
                    with self.state.lock:self.state.screen_frames={};self.state.screen_status=str(exc)
                    if str(exc)!=last_error:self.logger.warning('Screen: %s',exc);last_error=str(exc)
                    retry=time.monotonic()+2
        finally:
            if desktop:desktop.close()
            with self.state.lock:self.state.screen_frames={};self.state.screen_status='Idle'
    def join(self):
        if self.thread:self.thread.join(timeout=5)
