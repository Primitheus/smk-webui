"""On-demand WASAPI capture; only transient spectrum levels reach the engine."""
import ctypes
from pathlib import Path
import threading
import time

AUDIO_TYPES=('Audio Spectrum','Audio Pulse')

def wanted(state):
    with state.lock:
        if state.mode!=8:return False
        solo=state.solo_index if time.monotonic()<state.solo_until else None
        return any(p['type'] in AUDIO_TYPES and (i==solo if solo is not None else p['enabled']) for i,p in enumerate(state.studio['layers']))

class AudioCapture:
    def __init__(self,state,stop,logger):
        self.state=state;self.stop=stop;self.logger=logger;self.thread=None
    def start(self):
        self.thread=threading.Thread(target=self.run,name='system-audio',daemon=True);self.thread.start()
    def status(self,text,levels=None):
        with self.state.lock:
            self.state.audio_status=text
            if levels is not None:self.state.audio_bands=list(levels);self.state.audio_at=time.monotonic()
    def run(self):
        api=None;context=ctypes.c_void_p();retry=0;last_error=None
        try:
            while not self.stop.wait(.03):
                if not wanted(self.state):
                    if context.value:api.smk_audio_close(context);context=ctypes.c_void_p()
                    self.status('Idle',[0.]*16);retry=0;continue
                try:
                    if not context.value:
                        if time.monotonic()<retry:continue
                        retry=time.monotonic()+2
                        if api is None:
                            package=Path(__file__).resolve().parent
                            path=package/'audio_capture.dll'
                            if not path.is_file():path=package.parents[1]/'build/audio_capture.dll'
                            if not path.is_file():raise OSError('Audio capture helper is missing; rebuild the Windows package')
                            api=ctypes.CDLL(str(path));api.smk_audio_open.argtypes=[ctypes.POINTER(ctypes.c_void_p)];api.smk_audio_open.restype=ctypes.c_long
                            api.smk_audio_read.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_float)];api.smk_audio_read.restype=ctypes.c_long
                            api.smk_audio_close.argtypes=[ctypes.c_void_p];api.smk_audio_close.restype=None
                        result=api.smk_audio_open(ctypes.byref(context))
                        if result<0:raise OSError('Playback capture unavailable (0x%08X)'%(result&0xffffffff))
                        self.logger.info('System-audio capture started');last_error=None
                    levels=(ctypes.c_float*16)();result=api.smk_audio_read(context,levels)
                    if result<0:raise OSError('Playback device changed or disconnected (0x%08X)'%(result&0xffffffff))
                    self.status('Capturing' if max(levels)>.01 else 'Listening - No Audio',levels)
                except (OSError,AttributeError) as exc:
                    if context.value:api.smk_audio_close(context);context=ctypes.c_void_p()
                    self.status(str(exc),[0.]*16);retry=time.monotonic()+2
                    if str(exc)!=last_error:self.logger.warning('Audio: %s',exc);last_error=str(exc)
        finally:
            if context.value:api.smk_audio_close(context)
            self.status('Idle',[0.]*16)
    def join(self):
        if self.thread:self.thread.join(timeout=5)
