import ctypes
import math
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
from smk_webui import studio
from smk_webui.audio import wanted
from smk_webui.engine import State,KEYS

class AudioTests(unittest.TestCase):
    def test_auto_level_uses_keyboard_height_at_measured_music_level(self):
        state=State();state.mode=8
        state.studio={'version':1,'layers':[studio.layer('Audio Spectrum',sensitivity=2.2,noise_gate=.02,smoothing=.3)]}
        state.audio_bands=[.154]*16;state.audio_at=100;state.audio_tick=100
        with patch('smk_webui.engine.time.monotonic',return_value=100.03):state.frame(0)
        with patch('smk_webui.engine.time.monotonic',return_value=100.06):frame=state.frame(.03)
        top=next(k['cell'] for k in KEYS if k['y']==0)
        self.assertGreater(max(frame[top]),100)
        state.studio['layers'][0]['auto_level']=False;state.audio_smooth={}
        with patch('smk_webui.engine.time.monotonic',return_value=100.09):fixed=state.frame(.06)
        self.assertEqual(fixed[top],(0,0,0))
        state.studio['layers'][0]['auto_level']=True;state.audio_smooth={};state.audio_reference={};state.audio_bands=[.019]*16
        with patch('smk_webui.engine.time.monotonic',return_value=100.12):quiet=state.frame(.09)
        self.assertTrue(all(rgb==(0,0,0) for rgb in quiet))

    def test_capture_only_for_active_audio_layers(self):
        state=State();state.mode=8;state.studio={'version':1,'layers':[studio.layer('Audio Spectrum',enabled=False),studio.layer('Solid')]}
        self.assertFalse(wanted(state))
        state.solo_index=0;state.solo_until=time.monotonic()+5;self.assertTrue(wanted(state))
        state.solo_index=1;self.assertFalse(wanted(state))
        state.solo_index=None;state.studio['layers'][0]['enabled']=True;self.assertTrue(wanted(state))
        state.mode=3;self.assertFalse(wanted(state))

    def test_silence_spectrum_masks_and_pulse(self):
        scene={'version':1,'layers':[studio.layer('Audio Spectrum',mask='Custom',cells=[KEYS[-1]['cell']])]}
        self.assertTrue(all(rgb==(0,0,0) for rgb in studio.render(scene,KEYS,0,[],0)))
        frame=studio.render(scene,KEYS,0,[],0,audio={0:[1.]*16})
        self.assertNotEqual(frame[KEYS[-1]['cell']],(0,0,0))
        self.assertTrue(all(rgb==(0,0,0) for i,rgb in enumerate(frame) if i!=KEYS[-1]['cell']))
        scene['layers'][0]=studio.layer('Audio Pulse')
        frame=studio.render(scene,KEYS,0,[],0,audio={0:[.8]*16})
        self.assertTrue(all(0<=c<=255 for rgb in frame for c in rgb))
        self.assertTrue(any(max(rgb)>0 for rgb in frame))
        for name,value in [('sensitivity',5),('smoothing',-1),('noise_gate',float('nan'))]:
            scene['layers'][0]=studio.layer('Audio Pulse',**{name:value})
            with self.assertRaises(ValueError):studio.validate(scene)

    def test_smoothing_and_stale_capture_decay(self):
        state=State();state.mode=8;state.studio={'version':1,'layers':[studio.layer('Audio Pulse',smoothing=.8,auto_level=False)]}
        state.audio_bands=[1.]*16;state.audio_at=100;state.audio_tick=100
        with patch('smk_webui.engine.time.monotonic',return_value=100.03):state.frame(0)
        first=state.audio_smooth[0][0];self.assertTrue(.75<first<1)
        with patch('smk_webui.engine.time.monotonic',return_value=100.06):state.frame(.03)
        self.assertGreater(state.audio_smooth[0][0],first)
        self.assertGreater(state.audio_smooth[0][0],.95)
        state.audio_bands=[0.]*16
        with patch('smk_webui.engine.time.monotonic',return_value=100.09):state.frame(.06)
        self.assertGreater(state.audio_smooth[0][0],.5)
        for n in range(200):
            with patch('smk_webui.engine.time.monotonic',return_value=101+n*.03):frame=state.frame(n*.03)
        self.assertTrue(all(rgb==(0,0,0) for rgb in frame))

    @unittest.skipUnless(sys.platform=='win32' and (Path(__file__).parents[1]/'build/audio_capture_test.dll').exists(),'Build the optional native DSP test DLL')
    def test_native_frequency_bands(self):
        dll=ctypes.CDLL(str((Path(__file__).parents[1]/'build/audio_capture_test.dll').resolve()))
        dll.smk_audio_test.argtypes=[ctypes.POINTER(ctypes.c_float),ctypes.c_uint,ctypes.POINTER(ctypes.c_float)]
        for rate in (44100,48000,96000):
            for frequency in (100,1000,8000):
                samples=(ctypes.c_float*2048)(*(.7*math.sin(2*math.pi*frequency*i/rate) for i in range(2048)))
                bands=(ctypes.c_float*16)();dll.smk_audio_test(samples,rate,bands)
                expected=int(math.log(frequency/60,200)*16)
                self.assertLessEqual(abs(max(range(16),key=lambda i:bands[i])-expected),1)
                self.assertTrue(all(0<=v<=1 for v in bands))
        bands=(ctypes.c_float*16)();dll.smk_audio_test((ctypes.c_float*2048)(),48000,bands)
        self.assertEqual(list(bands),[0.]*16)
        peaks=[]
        for amplitude in (.01,.1,.5):
            samples=(ctypes.c_float*2048)(*(amplitude*math.sin(2*math.pi*1000*i/48000) for i in range(2048)))
            dll.smk_audio_test(samples,48000,bands);peaks.append(max(bands))
        self.assertGreater(peaks[1],peaks[0]*2.5)
        self.assertGreater(peaks[2],peaks[1]*2)

if __name__=='__main__':unittest.main()
