import json
from pathlib import Path
import tempfile
import threading
import unittest
import socket
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from smk_webui.application import Application
from smk_webui.server import Server
from smk_webui.engine import ripple_strength,key_codes,KEYS
from smk_webui.transport import frame_packets


class ApplicationTests(unittest.TestCase):
    def test_unfinished_workspace_survives_restart_without_overwriting_preset(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,True)
            app.patch({'mode':8})
            saved=app.preset('save',{'name':'Original'})
            baseline=json.loads(json.dumps(saved['settings']))
            app.save_workspace(dict(preset_id=saved['id'],workflow=dict(id=saved['id'],name='Original'),baseline=baseline))
            app.patch({'brightness':37})
            app.close()
            restored=Application(directory,True)
            try:
                self.assertEqual(restored.snapshot()['brightness']['8'],37)
                self.assertEqual(restored.info()['workspace']['workflow']['name'],'Original')
                self.assertEqual(restored.presets[0]['settings'],baseline)
                restored.preset('replace',{'id':saved['id']})
                self.assertIsNone(restored.workspace['workflow'])
                self.assertEqual(restored.presets[0]['settings']['brightness']['8'],37)
                restored.preset('delete',{'id':saved['id']})
                self.assertEqual(restored.workspace['preset_id'],'')
            finally:restored.close()

    def test_library_import_is_atomic_and_keeps_recovery_copy(self):
        original=self.app.preset('save',{'name':'Ripple'})
        library=self.app.export_library()
        invalid=json.loads(json.dumps(library))
        invalid['presets'].append({'name':'Broken','settings':None})
        before=(Path(self.directory.name)/'presets.json').read_bytes()
        with self.assertRaises((ValueError,TypeError)):self.app.import_library(invalid)
        self.assertEqual((Path(self.directory.name)/'presets.json').read_bytes(),before)
        result=self.app.import_library(library)
        self.assertEqual(result,{'imported':1})
        self.assertEqual([p['name'] for p in self.app.presets],['Ripple','Ripple (2)'])
        backups=list((Path(self.directory.name)/'preset-backups').glob('*.json'))
        self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text()),library)
        self.assertEqual(self.app.presets[0]['id'],original['id'])
        self.app.preset('delete',{'id':original['id']})
        self.app.import_library(json.loads(backups[0].read_text()))
        self.assertEqual(self.app.presets[-1]['name'],'Ripple')

    def test_preset_backups_are_bounded(self):
        saved=self.app.preset('save',{'name':'Keep'})
        for i in range(24):self.app.preset('rename',{'id':saved['id'],'name':f'Keep {i}'})
        self.assertEqual(len(list((Path(self.directory.name)/'preset-backups').glob('*.json'))),20)

    def test_invalid_workspace_does_not_replace_draft(self):
        before=self.app.info()['workspace']
        with self.assertRaises(ValueError):self.app.save_workspace(dict(preset_id='',workflow={'name':''},baseline=None))
        self.assertEqual(self.app.info()['workspace'],before)

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.app=Application(self.directory.name,True)
        self.addCleanup(self.app.close)

    def test_preset_cards_receive_saved_settings(self):
        self.app.patch({'mode':7,'foreground':[20,40,60]})
        saved=self.app.preset('save',{'name':'Ripple'})
        listed=self.app.info()['presets'][0]
        self.assertEqual(listed['settings'],json.loads(json.dumps(saved['settings'])))
        self.assertEqual(listed['settings']['mode'],7)
        listed['settings']['mode']=0
        self.assertEqual(self.app.info()['presets'][0]['settings']['mode'],7)

    def test_lighting_write_failure_clears_stale_device_state(self):
        from unittest.mock import patch
        app=self.app;app.demo=False;app.patch({'mode':0})
        class Control:
            capabilities={'version':'2.2'}
            def command(self,*args):return bytes((0,10,8))
        class Device:
            control=Control()
            def send(self,frame):raise OSError('Unplugged')
            def close(self):raise RuntimeError('Already closed')
        class Timer:
            def wait(self,delay):app.stop.set()
            def close(self):pass
        with patch('smk_webui.application.ciy_x77.open_device',return_value=Device()), \
             patch('smk_webui.application.socket.create_connection',side_effect=OSError), \
             patch('smk_webui.application.FrameTimer',Timer):app.run()
        self.assertFalse(app.connected)
        self.assertIsNone(app.capabilities)
        self.assertEqual(app.onboard_status,{})
        self.assertIn('Reconnecting',app.status)

    def test_onboard_status_disconnect_reopens_device(self):
        from unittest.mock import patch
        self.app.demo=False;self.app.patch({'mode':3})
        app=self.app;opened=[];clock=[0]
        class Control:
            capabilities={'version':'2.2'}
            def __init__(self,broken):self.broken=broken
            def command(self,*args):
                if self.broken:raise OSError('Disconnected')
                app.stop.set();return bytes((0,10,0))
        class Device:
            def __init__(self,broken):self.control=Control(broken);self.closed=False
            def close(self):self.closed=True
            def send(self,frame):pass
        def open_device():
            device=Device(not opened);opened.append(device);return device
        class Timer:
            def wait(self,delay):
                clock[0]+=3
                if len(opened)>3 or clock[0]>20:raise AssertionError('Reconnect did not complete')
            def close(self):pass
        with patch('smk_webui.application.ciy_x77.open_device',side_effect=open_device), \
             patch('smk_webui.application.socket.create_connection',side_effect=OSError), \
             patch('smk_webui.application.FrameTimer',Timer), \
             patch('smk_webui.application.time.monotonic',side_effect=lambda:clock[0]):
            app.run()
        self.assertEqual(len(opened),2)
        self.assertTrue(opened[0].closed)
        self.assertTrue(app.connected)

    def test_invalid_patch_is_atomic(self):
        before=self.app.snapshot()
        with self.assertRaises(ValueError):self.app.patch({'mode':7,'brightness':101})
        self.assertEqual(before,self.app.snapshot())

    def test_presets_roundtrip_and_names(self):
        self.app.patch({'mode':7,'foreground':[255,0,0],'background':[255,255,255]})
        p=self.app.preset('save',{'name':'Red ripple'})
        with self.assertRaises(ValueError):self.app.preset('save',{'name':'RED RIPPLE'})
        self.app.patch({'mode':0});self.app.preset('load',{'id':p['id']})
        self.assertEqual(self.app.snapshot()['mode'],7)
        other=Application(self.directory.name,True)
        self.addCleanup(other.close)
        self.assertEqual(other.presets[0]['name'],'Red ripple')
        self.assertNotIn('events',other.presets[0]['settings'])

    def test_corrupt_presets_preserved(self):
        path=Path(self.directory.name)/'presets.json';path.write_text('{broken')
        other=Application(self.directory.name,True)
        self.addCleanup(other.close)
        self.assertEqual(other.presets,[])
        self.assertTrue(list(path.parent.glob('presets.invalid-*.json')))

    def test_all_effect_frames(self):
        for mode in range(9):
            self.app.patch({'mode':mode});frame=self.app.state.frame(1.0)
            if mode==3:self.assertIsNone(frame)
            else:
                self.assertEqual(len(frame),108)
                packets=list(frame_packets(frame,255));self.assertEqual(len(packets),6)
                self.assertTrue(all(len(p)==64 for p in packets))
        self.assertEqual(ripple_strength(2,2,1.6,.1,2),1)

    def test_http_access_and_updates(self):
        server=Server(('127.0.0.1',0),self.app)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port)
        def request(path,data=None,token=None,origin=None):
            headers={'Content-Type':'application/json'}
            if token:headers['X-SMK-Token']=token
            if origin:headers['Origin']=origin
            return urlopen(Request(base+path,None if data is None else json.dumps(data).encode(),headers),timeout=3)
        with request('/api/session') as r:token=json.load(r)['token']
        with self.assertRaises(HTTPError) as error:request('/api/state')
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError):request('/api/settings',{'mode':7},token,'https://example.com')
        with request('/api/settings',{'mode':7,'brightness':50},token) as r:self.assertEqual(json.load(r)['mode'],7)
        for asset in ['/','/app.js','/studio.js','/controls.js','/style.css','/icon.svg']:
            with request(asset) as r:self.assertEqual(r.status,200)
        with request('/api/presets/builtin-0',token=token) as r:
            self.assertEqual(json.load(r)['settings']['mode'],8)
        with request('/api/previews',{'ids':['builtin-0'],'time':1},token) as r:
            self.assertEqual(len(json.load(r)['builtin-0']),108)
        with self.assertRaises(HTTPError):request('/../application.py')
        with request('/api/logs',token=token) as r:
            logs=json.load(r)
            self.assertIn('pid',logs)
            self.assertTrue(any('Settings applied' in line for line in logs['entries']))
        with self.assertRaises(HTTPError):request('/api/logs')

    def test_server_port_cannot_be_shared(self):
        server=Server(('127.0.0.1',0),self.app);self.addCleanup(server.server_close)
        with self.assertRaises(OSError):Server(server.server_address,self.app)
        other=socket.socket();self.addCleanup(other.close)
        other.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        with self.assertRaises(OSError):other.bind(server.server_address)

    def test_logs_are_bounded_and_exclude_input(self):
        for i in range(450):self.app.log.logger.info('Diagnostic %s',i)
        self.app.state.events.append((4,123))
        logs=self.app.diagnostics()
        self.assertEqual(len(logs['entries']),400)
        self.assertNotIn('events',logs)
        self.assertTrue(self.app.log.path.exists())

    def test_iso_punctuation_uses_active_layout(self):
        codes=key_codes(lambda scan:scan+1000)
        index=next(i for i,k in enumerate(KEYS) if k['cell']==86)
        self.assertEqual(codes[index],0x56+1000)
        self.assertLess(KEYS[index]['x'],next(k['x'] for k in KEYS if k['cell']==73))
        fallback=key_codes(lambda scan:0)
        self.assertEqual(fallback[index],226)


if __name__=='__main__':unittest.main()
