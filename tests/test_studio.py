import copy
import json
import tempfile
import unittest

from smk_webui import studio, settings
from smk_webui.application import Application
from smk_webui.engine import KEYS


class StudioTests(unittest.TestCase):
    def test_solo_is_temporary_and_never_saved(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,True)
            try:
                app.patch({'mode':8,'studio':dict(version=1,layers=[studio.layer('Solid',colour='#ff0000',enabled=False),studio.layer('Solid',colour='#0000ff')])})
                stored=copy.deepcopy(app.snapshot());cell=KEYS[0]['cell']
                with patch('smk_webui.application.time.monotonic',return_value=100):app.solo({'index':0})
                with patch('smk_webui.engine.time.monotonic',return_value=101):self.assertEqual(app.state.frame(0)[cell],(255,0,0))
                self.assertEqual(app.snapshot(),stored)
                self.assertEqual(app.preset('save',{'name':'Full Scene'})['settings'],stored)
                with patch('smk_webui.engine.time.monotonic',return_value=106):self.assertEqual(app.state.frame(0)[cell],(0,0,255))
                for value in (-1,2,True):
                    with self.assertRaises(ValueError):app.solo({'index':value})
                app.solo({'index':0});app.patch({'brightness':50})
                self.assertIsNone(app.state.solo_index)
                app.restore(stored);self.assertEqual(app.snapshot(),stored)
                invalid=copy.deepcopy(stored);invalid['mode']=99
                with self.assertRaises(ValueError):app.restore(invalid)
                self.assertEqual(app.snapshot(),stored)
            finally:app.close()

    def test_colour_boost_lifts_shadows_preserves_hue_and_output_limit(self):
        scene=dict(version=1,layers=[studio.layer('Solid',colour='#804020')])
        original=studio.render(scene,KEYS,0,[],0)[KEYS[0]['cell']]
        scene['boost']=100
        boosted=studio.render(studio.validate(scene),KEYS,0,[],0)[KEYS[0]['cell']]
        self.assertGreater(boosted[0],original[0])
        self.assertAlmostEqual(boosted[1]/boosted[0],.5,delta=.005)
        self.assertAlmostEqual(boosted[2]/boosted[0],.25,delta=.005)
        self.assertTrue(all(0<=c<=255 for c in boosted))
        for colour in ('#000000','#ff8040'):
            scene['layers'][0]['colour']=colour
            self.assertEqual(studio.render(scene,KEYS,0,[],0)[KEYS[0]['cell']],tuple(bytes.fromhex(colour[1:])))
        self.assertEqual(studio.render(scene,KEYS,0,[],0,0)[KEYS[0]['cell']],(0,0,0))
        for value in (-1,101,float('nan'),True):
            scene['boost']=value
            with self.assertRaises(ValueError):studio.validate(scene)

    def test_library_and_every_effect_render_bounded_frames(self):
        scenes=[dict(version=1,layers=layers) for _,layers in studio.library()]
        scenes += [dict(version=1,layers=[studio.layer(kind)]) for kind in studio.TYPES]
        for scene in scenes:
            validated=studio.validate(scene)
            for t in (0,.5,2,50):
                frame=studio.render(validated,KEYS,t,[(0,t-.1)],t)
                self.assertEqual(len(frame),108)
                self.assertTrue(all(type(c) is int and 0<=c<=255 for rgb in frame for c in rgb))

    def test_blending_masks_and_visibility(self):
        cell=KEYS[0]['cell']
        base=studio.layer('Solid',colour='#ff0000')
        overlay=studio.layer('Solid',colour='#0000ff',opacity=50,mask='Custom',cells=[cell])
        scene=dict(version=1,layers=[base,overlay])
        frame=studio.render(scene,KEYS,0,[],0)
        self.assertEqual(frame[cell],(128,0,128))
        self.assertEqual(frame[KEYS[1]['cell']],(255,0,0))
        overlay['blend']='Add'
        self.assertEqual(studio.render(scene,KEYS,0,[],0)[cell],(255,0,128))
        overlay['enabled']=False
        self.assertEqual(studio.render(scene,KEYS,0,[],0)[cell],(255,0,0))

    def test_invalid_scene_rejected_before_settings_change(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,True)
            try:
                before=app.snapshot()
                for change in ({'colour':'#ff ff '},{'speed':float('nan')},{'cells':[108]},{'code':'run()'},{'type':'Executable'}):
                    with self.assertRaises(ValueError):app.patch({'mode':8,'studio':dict(version=1,layers=[studio.layer(**change)])})
                    self.assertEqual(app.snapshot(),before)
                with self.assertRaises(ValueError):studio.validate(dict(version=1,layers=[studio.layer()]*9))
            finally:app.close()

    def test_legacy_settings_and_builtin_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,True)
            try:
                old=json.loads(json.dumps(app.snapshot()))
                old.pop('studio');old['brightness'].pop('8');old['speeds'].pop('8')
                self.assertEqual(settings.validate(old)['brightness'][8],100)
                preset=app.library()[0]
                app.preset('load',{'id':preset['id']})
                before=copy.deepcopy(app.snapshot())
                frames=app.previews({'ids':[preset['id']],'time':1})
                self.assertEqual(len(frames[preset['id']]),108)
                self.assertEqual(before,app.snapshot())
                saved=app.preset('save',{'name':'My Aurora'})
                self.assertEqual(saved['settings']['mode'],8)
                with self.assertRaises(ValueError):app.preset('delete',{'id':preset['id']})
            finally:app.close()


if __name__=='__main__':unittest.main()
