"""Precise Windows frame waits and timing-only diagnostics; no USB or input access."""
import ctypes as c
from ctypes import wintypes as w
from collections import deque
import math
import statistics


class FrameTimer:
    def __init__(self):
        self.kernel=c.WinDLL('kernel32',use_last_error=True)
        definitions=[
            ('CreateWaitableTimerExW',w.HANDLE,[w.LPVOID,w.LPCWSTR,w.DWORD,w.DWORD]),
            ('SetWaitableTimer',w.BOOL,[w.HANDLE,c.POINTER(c.c_longlong),w.LONG,w.LPVOID,w.LPVOID,w.BOOL]),
            ('WaitForSingleObject',w.DWORD,[w.HANDLE,w.DWORD]),
            ('CloseHandle',w.BOOL,[w.HANDLE]),
        ]
        for name,result,args in definitions:
            fn=getattr(self.kernel,name);fn.restype=result;fn.argtypes=args
        self.handle=self.kernel.CreateWaitableTimerExW(None,None,2,0x1f0003)
        if not self.handle: raise c.WinError(c.get_last_error())

    def wait(self,seconds):
        if seconds<=0: return
        due=c.c_longlong(-max(1,round(seconds*10_000_000)))
        if not self.kernel.SetWaitableTimer(self.handle,c.byref(due),0,None,None,False):
            raise c.WinError(c.get_last_error())
        if self.kernel.WaitForSingleObject(self.handle,math.ceil(seconds*1000)+1000)!=0:
            raise RuntimeError('Frame timer did not signal')

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle=None


class FrameTiming:
    def __init__(self): self.samples=deque(maxlen=240)
    def add(self,start,transfer_seconds): self.samples.append((start,transfer_seconds))
    def clear(self): self.samples.clear()
    def summary(self,target):
        if len(self.samples)<2: return None
        samples=list(self.samples)
        intervals=[b[0]-a[0] for a,b in zip(samples,samples[1:])]
        return dict(target_fps=target,measured_submission_fps=(len(samples)-1)/(samples[-1][0]-samples[0][0]),
                    mean_frame_interval_ms=1000*statistics.mean(intervals),
                    max_frame_interval_ms=1000*max(intervals),
                    p95_frame_interval_ms=1000*sorted(intervals)[math.ceil(.95*len(intervals))-1],
                    mean_transfer_ms=1000*statistics.mean(s[1] for s in samples),
                    frames_in_window=len(samples),note='Host submission timing; not measured physical LED refresh')
