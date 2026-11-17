"""Lighting effects, transient key events and saved settings."""
from collections import deque
import colorsys
import ctypes
import json
import math
from pathlib import Path
import threading
import time
import shutil
import uuid

ROOT = Path(__file__).resolve().parent
from . import settings, studio
from .screen import signature
KEYS = json.loads((ROOT/'devices/ciy_x77_iso.json').read_text())
MODES = ('Static','Colour Cycle (PC)','Breathing (PC)','Onboard Lighting',
         'Rainbow Wave (PC)','Vertical Wave (PC)','Reactive Typing (PC)','Typing Ripple (PC)','Layer Studio')


def ripple_strength(distance,radius,width,age,duration):
    # An opaque ring core replaces the background. Only the outer 35% of
    # the band and the final 20% of its lifetime crossfade back to it.
    edge=max(0,min(1,(width-abs(distance-radius))/(width*.35)))
    tail=max(0,min(1,(duration-age)/(duration*.2)))
    return (edge*edge*(3-2*edge))*(tail*tail*(3-2*tail))


class State:
    def __init__(self, settings_path=None):
        self.lock=threading.Lock()
        self.studio={"version":1,"layers":[studio.layer()]}
        self.mode=3
        self.screen_frames={};self.screen_smooth={};self.screen_status="Idle"
        self.audio_bands=[0.]*16;self.audio_at=0;self.audio_status="Idle"
        self.audio_smooth={};self.audio_reference={};self.audio_tick=0
        self.solo_index=None
        self.solo_until=0
        self.clients=1
        self.colours = [(191,64,255)]*88
        self.events = deque(maxlen=24)
        self.speeds = {index:5 for index in (1,2,4,5,6,7,8)}
        self.brightness = {index:100 for index in range(len(MODES)) if index!=3}
        self.reactive_colours = {6:(51,163,255),7:(51,163,255)}
        self.background_colours = {6:(0,0,0),7:(0,0,0)}
        self.directions = {4:1,5:3}
        self.effect_options = dict(settings.DEFAULT_OPTIONS)
        self.settings_path=Path(settings_path) if settings_path else None
        self.settings_notice=None
        self._invalid_settings=False
        self._revision=0
        self._saved_revision=0
        self._changed_at=0
        self._last_save_attempt=0
        if self.settings_path and self.settings_path.exists():
            try:
                restored=settings.validate(json.loads(self.settings_path.read_text(encoding='utf-8')))
                for key,value in restored.items(): setattr(self,key,value)
            except (OSError,ValueError,TypeError) as exc:
                self.settings_notice=f'Could not restore lighting settings; using defaults: {exc}'
                self._invalid_settings=True
        self.preferred_mode=self.mode

    def changed(self):
        self._revision+=1
        self._changed_at=time.monotonic()

    def save_settings(self,force=False):
        if self.settings_path is None: return
        now=time.monotonic()
        with self.lock:
            if self._revision==self._saved_revision: return
            if not force and (now-self._last_save_attempt<1 or
                              (now-self._changed_at<.5 and now-self._last_save_attempt<5)): return
            self._last_save_attempt=now
            revision=self._revision
            snapshot=dict(version=1,mode=self.preferred_mode,colours=list(self.colours),
                          speeds={str(k):v for k,v in self.speeds.items()},
                          brightness={str(k):v for k,v in self.brightness.items()},
                          reactive_colours={str(k):v for k,v in self.reactive_colours.items()},
                          background_colours={str(k):v for k,v in self.background_colours.items()},
                          directions={str(k):v for k,v in self.directions.items()},
                          effect_options=dict(self.effect_options),studio=self.studio)
        if self._invalid_settings and self.settings_path.exists():
            backup=self.settings_path.with_name(self.settings_path.name+'.invalid-'+uuid.uuid4().hex+'.bak')
            shutil.copyfile(self.settings_path,backup)
            self._invalid_settings=False
        settings.save(self.settings_path,snapshot)
        with self.lock: self._saved_revision=revision

    def frame(self,elapsed):
        with self.lock:
            mode,colours,events,clients = self.mode,list(self.colours),list(self.events),self.clients
            speed=self.speeds.get(mode,5)
            brightness=self.brightness.get(mode,100)/100
            reactive_colour=self.reactive_colours.get(mode,(51,163,255))
            background=self.background_colours.get(mode,(0,0,0))
            direction=self.directions.get(mode,1)
            options=dict(self.effect_options)
            scene=self.studio
            now=time.monotonic();dt=max(0,min(.25,now-self.audio_tick));self.audio_tick=now
            raw=self.audio_bands if now-self.audio_at<.5 else [0.]*16
            audio={}
            for i,p in enumerate(scene['layers']):
                if p['type'] in ('Audio Spectrum','Audio Pulse'):
                    # Gate before gain; retain a recent peak so dynamics within
                    # a passage remain visible. Never amplify more than 8x.
                    gate=p.get('noise_gate',.05)
                    peak=max(0,max(raw)-gate)
                    reference=max(peak,self.audio_reference.get(i,0)*math.exp(-dt/4))
                    self.audio_reference[i]=reference
                    gain=min(8,.45/max(.02,reference)) if p.get('auto_level',True) else 1
                    adjusted=[(v-gate)*gain+gate if v>gate else 0 for v in raw]
                    smoothing=p.get('smoothing',.6)
                    attack=1-math.exp(-dt/(.012+.008*smoothing))
                    release=1-math.exp(-dt/(.04+.3*smoothing))
                    previous=self.audio_smooth.get(i,[0.]*16)
                    audio[i]=[old+(value-old)*(attack if value>old else release) for old,value in zip(previous,adjusted)]
            self.audio_smooth=audio
            screen={}
            for i,p in enumerate(scene['layers']):
                if p['type']=='Screen Colours':
                    entry=self.screen_frames.get(signature(p))
                    if entry and now-entry[1]<.5:
                        target=entry[0];previous=self.screen_smooth.get(i,target)
                        weight=1-math.exp(-dt/(.015+.6*p.get('smoothing',.6)))
                        screen[i]=[tuple(old[j]+(new[j]-old[j])*weight for j in range(3)) for old,new in zip(previous,target)]
            self.screen_smooth=screen
            solo=self.solo_index if time.monotonic()<self.solo_until else None
        if mode==3 or not clients: return None
        if mode==8:
            if solo is not None and solo<len(scene['layers']):
                scene={**scene,'layers':[{**scene['layers'][solo],'enabled':True}]}
                audio={0:audio.get(solo,[0.]*16)}
                screen={0:screen[solo]} if solo in screen else {}
            now=time.monotonic()
            scaled_events=[(index,now-(now-stamp)*speed/5) for index,stamp in events]
            return studio.render(scene,KEYS,elapsed*speed/5,scaled_events,now,brightness,audio,screen)
        pixels=[(0,0,0)]*108
        now=time.monotonic()
        for index,key in enumerate(KEYS):
            rgb=colours[index]
            if mode in (1,4):
                offset=key['x']/18 if mode==4 else 0
                period=12/speed if mode==4 else 40/speed
                motion=-1 if mode==4 and direction==0 else 1
                rgb=tuple(round(v*255) for v in colorsys.hsv_to_rgb((motion*elapsed/period-offset)%1,1,1))
            elif mode==5:
                # Same broad wavelength as horizontal, with smooth channel slopes.
                # A full rainbow across only six rows made adjacent bands abrupt.
                phase=(1 if direction==3 else -1)*elapsed/(12/speed)-key['y']/18
                channels=tuple(1+math.cos(math.tau*(phase-offset)) for offset in (0,1/3,2/3))
                peak=max(channels)
                rgb=tuple(round(255*v/peak) for v in channels)
            elif mode==2:
                level=(1-math.cos(elapsed*math.tau/(20/speed)))/2
                rgb=tuple(round(v*level) for v in rgb)
            elif mode in (6,7):
                level=0
                for event_index,stamp in events:
                    age=now-stamp
                    duration=options['reactive_fade' if mode==6 else 'ripple_fade']*5/speed
                    if not 0<=age<duration: continue
                    origin=KEYS[event_index]
                    distance=math.hypot(key['x']-origin['x'],(key['y']-origin['y'])*1.2)
                    value=max(0,1-age/duration) if mode==6 and index==event_index else 0
                    if mode==7: value=ripple_strength(distance,age*9*speed/5,options['ripple_width'],age,duration)
                    level=max(level,value)
                rgb=tuple(round(bg+(fg-bg)*level) for fg,bg in zip(reactive_colour,background))
            pixels[key['cell']]=tuple(round(v*brightness) for v in rgb)
        return pixels


def monitor_keys(state,stop):
    # Only transient key-down positions, while a reactive mode is active.
    # No text reconstruction, key logging, files, network transmission or hooks.
    user32=ctypes.WinDLL('user32')
    user32.GetAsyncKeyState.argtypes=[ctypes.c_int]
    user32.GetAsyncKeyState.restype=ctypes.c_short
    user32.GetForegroundWindow.restype=ctypes.c_void_p
    user32.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype=ctypes.c_ulong
    user32.GetKeyboardLayout.argtypes=[ctypes.c_ulong]
    user32.GetKeyboardLayout.restype=ctypes.c_void_p
    user32.MapVirtualKeyExW.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p]
    user32.MapVirtualKeyExW.restype=ctypes.c_uint
    layout=None;codes=[key['vk'] for key in KEYS]
    down=set()
    was_active=False
    while not stop.wait(0.008):
        with state.lock: active=(state.mode in (6,7) or state.mode==8 and any((p['enabled'] or (i==state.solo_index and time.monotonic()<state.solo_until)) and p['type'] in ('Ripple','Reactive') for i,p in enumerate(state.studio['layers']))) and state.clients>0
        if not active:
            down.clear()
            was_active=False
            continue
        foreground=user32.GetForegroundWindow()
        thread=user32.GetWindowThreadProcessId(foreground,None)
        active_layout=user32.GetKeyboardLayout(thread)
        if active_layout!=layout:
            layout=active_layout
            codes=key_codes(lambda scan:user32.MapVirtualKeyExW(scan,3,layout))
            down.clear();was_active=False
        current={i for i,code in enumerate(codes) if code and user32.GetAsyncKeyState(code) & 0x8000}
        if was_active:
            with state.lock:
                for index in current-down: state.events.append((index,time.monotonic()))
        down=current
        was_active=True


def key_codes(map_scan):
    # OEM virtual-key numbers depend on the active Windows keyboard layout.
    # Physical scan codes keep ISO punctuation, including IntlBackslash, distinct.
    scans={18:0x29,29:0x0c,30:0x0d,47:0x1a,48:0x1b,
           64:0x27,65:0x28,66:0x2b,86:0x56,80:0x33,81:0x34,82:0x35}
    return [(map_scan(scans[key['cell']]) or key['vk']) if key['cell'] in scans else key['vk'] for key in KEYS]
