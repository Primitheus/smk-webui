import math
import ctypes as c
import sys
import threading
import unittest
from unittest.mock import patch
from smk_webui import studio
from smk_webui.engine import State,KEYS
from smk_webui.screen import requests,region_bounds,reduce_bgra,signature,WIDTH,HEIGHT,ScreenCapture,Desktop,BitmapInfo

class ScreenTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='win32','Windows graphics API')
    def test_native_sampling_from_synthetic_bitmap(self):
        # Two in-memory DIBs: this does not acquire or sample the desktop.
        desktop=Desktop();source=None;bitmap=None;previous=None
        try:
            source=desktop.gdi.CreateCompatibleDC(None);self.assertTrue(source)
            info=BitmapInfo();info.size=c.sizeof(info);info.width=WIDTH;info.height=-HEIGHT;info.planes=1;info.bits=32
            bits=c.c_void_p();bitmap=desktop.gdi.CreateDIBSection(source,c.byref(info),0,c.byref(bits),None,0);self.assertTrue(bitmap)
            previous=desktop.gdi.SelectObject(source,bitmap)
            data=bytes(v for y in range(HEIGHT) for x in range(WIDTH) for v in ((0,0,255,0) if x<WIDTH//2 else (255,0,0,0)))
            c.memmove(bits,data,len(data));desktop.source=source
            desktop.memory=desktop.gdi.CreateCompatibleDC(source)
            desktop.bitmap=desktop.gdi.CreateDIBSection(source,c.byref(info),0,c.byref(desktop.bits),None,0)
            desktop.previous=desktop.gdi.SelectObject(desktop.memory,desktop.bitmap)
            pixels=desktop.sample((0,0,WIDTH,HEIGHT))
            self.assertEqual(pixels[0],(255,0,0));self.assertEqual(pixels[-1],(0,0,255))
        finally:
            desktop.source=None;desktop.close()
            if source and previous:desktop.gdi.SelectObject(source,previous)
            if bitmap:desktop.gdi.DeleteObject(bitmap)
            if source:desktop.gdi.DeleteDC(source)

    def test_region_bounds_negative_origin_and_validation(self):
        monitor={'bounds':[-1920,0,0,1080]}
        self.assertEqual(region_bounds(monitor,[50,0,50,100]),(-960,0,960,1080))
        scene={'version':1,'layers':[studio.layer('Screen Colours')]}
        for region in ([90,0,20,100],[0,0,0,100],[0,float('nan'),100,100],[-1,0,100,100]):
            scene['layers'][0]['screen_region']=region
            with self.assertRaises(ValueError):studio.validate(scene)

    def test_sampling_preserves_top_down_rgb_zones(self):
        data=bytearray()
        for y in range(HEIGHT):
            for x in range(WIDTH):data.extend((30,y//4,x//4,255))
        grid=reduce_bgra(data)
        self.assertEqual(len(grid),108)
        self.assertEqual(grid[0],(0,0,30));self.assertEqual(grid[-1],(17,5,30))
        with self.assertRaises(ValueError):reduce_bgra(b'')

    def test_screen_render_and_stale_capture(self):
        state=State();state.mode=8;layer=studio.layer('Screen Colours',smoothing=0)
        state.studio={'version':1,'layers':[layer]}
        grid=[(255,0,0) if i%18<9 else (0,0,255) for i in range(108)]
        state.screen_frames[signature(layer)]=(grid,100)
        with patch('smk_webui.engine.time.monotonic',return_value=100.1):frame=state.frame(0)
        left=next(k for k in KEYS if k['x']<9);right=next(k for k in KEYS if k['x']>=9)
        self.assertEqual(frame[left['cell']],(255,0,0));self.assertEqual(frame[right['cell']],(0,0,255))
        layer['screen_mode']='Average'
        with patch('smk_webui.engine.time.monotonic',return_value=100.2):frame=state.frame(.1)
        self.assertEqual(frame[left['cell']],(128,0,128))
        layer['saturation']=0
        with patch('smk_webui.engine.time.monotonic',return_value=100.3):frame=state.frame(.2)
        self.assertEqual(frame[left['cell']],(128,128,128))
        with patch('smk_webui.engine.time.monotonic',return_value=101):frame=state.frame(1)
        self.assertTrue(all(rgb==(0,0,0) for rgb in frame))

    def test_requests_respect_disabled_layers_and_solo(self):
        state=State();state.mode=8;state.studio={'version':1,'layers':[studio.layer('Screen Colours',enabled=False),studio.layer('Solid')]}
        self.assertFalse(requests(state))
        state.solo_index=0;state.solo_until=math.inf;self.assertEqual(len(requests(state)),1)
        state.solo_index=1;self.assertFalse(requests(state))
        state.mode=3;self.assertFalse(requests(state))

    def test_worker_releases_capture_and_never_keeps_failed_frames(self):
        state=State();state.mode=8;state.studio={'version':1,'layers':[studio.layer('Screen Colours')]}
        closed=[]
        class Stop:
            ticks=0
            def wait(self,delay):
                self.ticks+=1
                if self.ticks==2:
                    self.assert_frame=bool(state.screen_frames);state.mode=4
                if self.ticks==3:
                    assert not state.screen_frames
                    return True
                return False
        class Desktop:
            def monitors(self):return [{'id':'test','primary':True,'bounds':[0,0,1920,1080]}]
            def sample(self,bounds):return [(10,20,30)]*108
            def close(self):closed.append(True)
        stop=Stop()
        with patch('smk_webui.screen.Desktop',Desktop):ScreenCapture(state,stop,None).run()
        self.assertTrue(stop.assert_frame);self.assertEqual(closed,[True]);self.assertEqual(state.screen_status,'Idle')

if __name__=='__main__':unittest.main()
