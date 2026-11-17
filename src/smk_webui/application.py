"""Application state, presets and the background lighting worker."""
import json
import math
import os
from pathlib import Path
import socket
import threading
import time
import uuid
import queue
from concurrent.futures import Future

from .engine import State, MODES, monitor_keys
from .settings import validate, validate_options
from .pacing import FrameTimer, FrameTiming
from .devices import ciy_x77
from .diagnostics import Diagnostics
from . import onboard, studio
from . import __version__
from .audio import AudioCapture
from .screen import ScreenCapture,signature


def atomic_json(path,value):
    temporary=path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


class Application:
    def __init__(self,data_dir,demo=False):
        self.data_dir=Path(data_dir);self.data_dir.mkdir(parents=True,exist_ok=True)
        self.log=Diagnostics(self.data_dir)
        self.state=State(self.data_dir/'settings.json')
        self.state.clients=1 # The engine belongs to the app, not a browser/SDK connection.
        self.stop=threading.Event();self.lock=threading.RLock();self.demo=demo
        self.status='Preview mode' if demo else 'Looking for keyboard'
        self.connected=False;self.fps=0;self.preview=[(0,0,0)]*108
        self.presets=[];self.worker=None;self.audio=AudioCapture(self.state,self.stop,self.log.logger);self.screen=ScreenCapture(self.state,self.stop,self.log.logger);self.notice=self.state.settings_notice
        self.capabilities=None;self.onboard_status={};self.jobs=queue.Queue();self.claim_requested=True;self.last_direct_mode=self.state.mode if self.state.mode!=3 else 0
        path=self.data_dir/'presets.json'
        if path.exists():
            try:
                values=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(values,list):raise ValueError('Invalid preset list')
                ids=set();names=set()
                for item in values:
                    uuid.UUID(item['id']);self.check_name(item['name']);validate(item['settings'])
                    if item['id'] in ids or item['name'].casefold() in names:raise ValueError('Duplicate preset')
                    ids.add(item['id']);names.add(item['name'].casefold())
                self.presets=values
            except (ValueError,TypeError,KeyError,OSError) as exc:
                # Preserve a damaged file before allowing future saves.
                backup=path.with_name('presets.invalid-'+uuid.uuid4().hex+'.json')
                backup.write_bytes(path.read_bytes())
                self.notice=f'Could not load presets. Original preserved as {backup.name}: {exc}'

        self.workspace=dict(preset_id='',workflow=None,baseline=None)
        path=self.data_dir/'workspace.json'
        if path.exists():
            try:self.workspace=self.validate_workspace(json.loads(path.read_text(encoding='utf-8')))
            except (ValueError,TypeError,KeyError,OSError) as exc:
                self.log.logger.warning('Could not restore Studio workspace: %s',exc)

    def validate_workspace(self,data):
        if not isinstance(data,dict) or set(data)!={'preset_id','workflow','baseline'}:raise ValueError('Invalid Studio workspace')
        if not isinstance(data['preset_id'],str) or len(data['preset_id'])>64:raise ValueError('Invalid preset ID')
        workflow=data['workflow']
        if workflow is not None:
            if not isinstance(workflow,dict) or set(workflow)!={'id','name'}:raise ValueError('Invalid draft')
            if workflow['id'] is not None and (not isinstance(workflow['id'],str) or len(workflow['id'])>64):raise ValueError('Invalid draft ID')
            self.check_name(workflow['name'])
        if data['baseline'] is not None:validate(data['baseline'])
        return json.loads(json.dumps(data))

    def save_workspace(self,data):
        with self.lock:
            value=self.validate_workspace(data)
            self.state.save_settings(force=True)
            atomic_json(self.data_dir/'workspace.json',value);self.workspace=value
        return json.loads(json.dumps(value))

    @staticmethod
    def check_name(name):
        if not isinstance(name,str) or not name.strip() or len(name.strip())>64:raise ValueError('Use a preset name between 1 and 64 characters')
        return name.strip()

    def snapshot(self):
        with self.state.lock:
            s=self.state
            return dict(version=1,mode=s.preferred_mode,colours=list(s.colours),
                        speeds={str(k):v for k,v in s.speeds.items()},brightness={str(k):v for k,v in s.brightness.items()},
                        reactive_colours={str(k):v for k,v in s.reactive_colours.items()},
                        background_colours={str(k):v for k,v in s.background_colours.items()},
                        directions={str(k):v for k,v in s.directions.items()},effect_options=dict(s.effect_options),studio=json.loads(json.dumps(s.studio)))

    def apply(self,snapshot):
        restored=validate(snapshot)
        with self.state.lock:
            for key,value in restored.items():setattr(self.state,key,value)
            self.state.solo_index=None;self.state.solo_until=0;self.state.audio_smooth={};self.state.audio_reference={};self.state.screen_smooth={}
            self.state.preferred_mode=self.state.mode
            self.state.events.clear();self.state.changed()
        self.log.logger.info('Settings applied; effect=%s',MODES[self.state.mode])
        self.claim_requested=self.state.mode!=3
        if self.state.mode!=3:self.last_direct_mode=self.state.mode

    def solo(self,data):
        if not isinstance(data,dict) or set(data)!={'index'}:raise ValueError('Expected a solo layer index')
        index=data['index']
        with self.lock,self.state.lock:
            if index is not None and (type(index) is not int or self.state.mode!=8 or not 0<=index<len(self.state.studio['layers'])):raise ValueError('Invalid solo layer')
            self.state.solo_index=index;self.state.solo_until=time.monotonic()+5 if index is not None else 0
        return dict(index=index)

    def restore(self,data):
        with self.lock:self.apply(data)
        return self.snapshot()

    def patch(self,patch):
        if not isinstance(patch,dict):raise ValueError('Settings must be an object')
        allowed={'mode','speed','brightness','foreground','background','direction','effect_options','key_colour','studio'}
        if set(patch)-allowed:raise ValueError('Unknown setting')
        # Serialize UI writes so simultaneous controls cannot overwrite each other.
        with self.lock:
            value=self.snapshot();mode=patch.get('mode',value['mode'])
            if type(mode) is not int or not 0<=mode<len(MODES):raise ValueError('Invalid effect')
            value['mode']=mode
            for field,target in (('speed','speeds'),('brightness','brightness'),('foreground','reactive_colours'),('background','background_colours'),('direction','directions')):
                if field in patch:
                    if str(mode) not in value[target]:raise ValueError('Control is unavailable for this effect')
                    value[target][str(mode)]=patch[field]
            if 'studio' in patch:value['studio']=studio.validate(patch['studio'])
            if 'effect_options' in patch:value['effect_options']=validate_options({**value['effect_options'],**patch['effect_options']})
            if 'key_colour' in patch:
                selection=patch['key_colour']
                if not isinstance(selection,dict) or set(selection)!={'indices','rgb'}:raise ValueError('Invalid key colour')
                indices=selection['indices']
                if not isinstance(indices,list) or not indices:raise ValueError('Select at least one key')
                for i in indices:
                    if type(i) is not int or not 0<=i<len(value['colours']):raise ValueError('Invalid key index')
                    value['colours'][i]=selection['rgb']
            self.apply(value)
        return self.snapshot()

    def export_library(self):
        with self.lock:
            return dict(format='smk-webui-library',version=1,presets=[dict(name=p['name'],settings=json.loads(json.dumps(p['settings']))) for p in self.presets])

    def backup_presets(self):
        if not self.presets:return
        folder=self.data_dir/'preset-backups';folder.mkdir(exist_ok=True)
        path=folder/('library-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json')
        atomic_json(path,self.export_library())
        for old in sorted(folder.glob('library-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[20:]:old.unlink()

    def import_library(self,data):
        if not isinstance(data,dict) or data.get('format')!='smk-webui-library' or data.get('version')!=1 or not isinstance(data.get('presets'),list) or not 1<=len(data['presets'])<=100:raise ValueError('Import 1–100 presets at a time')
        with self.lock:
            items=json.loads(json.dumps(self.presets));names={p['name'].casefold() for p in items}
            for entry in data['presets']:
                if not isinstance(entry,dict):raise ValueError('Invalid library entry')
                name=self.check_name(entry.get('name'));validate(entry.get('settings'))
                base=name;number=2
                while name.casefold() in names:
                    suffix=f' ({number})';name=base[:64-len(suffix)]+suffix;number+=1
                names.add(name.casefold());items.append(dict(id=str(uuid.uuid4()),name=name,settings=entry['settings']))
            self.backup_presets();atomic_json(self.data_dir/'presets.json',items);self.presets=items
        return dict(imported=len(data['presets']))

    def preset(self,action,data):
        if not isinstance(data,dict):raise ValueError('Invalid preset request')
        if action=='import-library':return self.import_library(data)
        with self.lock:
            items=json.loads(json.dumps(self.presets))
            item=next((p for p in items+self.library() if p['id']==data.get('id')),None)
            if item and item.get('builtin') and action in ('rename','delete','replace'):raise ValueError('Duplicate a built-in preset before changing it')
            if action in ('load','rename','delete','replace','duplicate') and item is None:raise ValueError('Preset not found')
            if action=='load':
                self.apply(item['settings'])
                self.save_workspace(dict(preset_id=item['id'],workflow=None,baseline=self.snapshot()))
                return item
            if action in ('save','import','duplicate','rename'):
                name=self.check_name(data.get('name'))
                if any(p['name'].casefold()==name.casefold() and not(action=='rename' and p['id']==item['id']) for p in items):raise ValueError('A preset with that name already exists')
            if action in ('save','import','duplicate'):
                snapshot=data.get('settings') if action=='import' else item['settings'] if action=='duplicate' else self.snapshot()
                validate(snapshot)
                item=dict(id=str(uuid.uuid4()),name=name,settings=snapshot);items.append(item)
            elif action=='rename':item['name']=name
            elif action=='delete':items.remove(item)
            elif action=='replace':item['settings']=self.snapshot()
            else:raise ValueError('Unknown preset action')
            self.backup_presets();atomic_json(self.data_dir/'presets.json',items);self.presets=items
            if action in ('save','replace'):
                self.save_workspace(dict(preset_id=item['id'],workflow=None,baseline=self.snapshot()))
            elif action=='delete' and self.workspace['preset_id']==item['id']:
                self.save_workspace(dict(preset_id='',workflow=None,baseline=None))
            return item

    def library(self):
        base=self.snapshot();result=[]
        for i,(name,layers) in enumerate(studio.library()):
            settings=json.loads(json.dumps(base));settings['mode']=8;settings['studio']={'version':1,'layers':layers};settings['brightness']['8']=100;settings['speeds']['8']=5
            settings['studio']['boost']=40 if name=='Sunset Orbit' else 0
            result.append(dict(id='builtin-'+str(i),name=name,settings=settings,builtin=True))
        return result

    def previews(self,data):
        if not isinstance(data,dict):raise ValueError('Expected a preview request')
        ids=data.get('ids');elapsed=data.get('time',0)
        if not isinstance(ids,list) or len(ids)>12 or any(not isinstance(i,str) for i in ids):raise ValueError('Expected up to 12 preset IDs')
        if type(elapsed) not in (int,float) or not 0<=elapsed<100000:raise ValueError('Invalid preview time')
        catalog={p['id']:p for p in self.presets+self.library()};frames={}
        for identifier in ids:
            if identifier not in catalog:continue
            preview=State();restored=validate(catalog[identifier]['settings'])
            for key,value in restored.items():setattr(preview,key,value)
            now=time.monotonic();tick=int(elapsed/1.2)
            preview.audio_bands=[.35+.3*math.sin(elapsed*3+i*.5) for i in range(16)];preview.audio_at=now
            for layer in preview.studio['layers']:
                if layer['type']=='Screen Colours':preview.screen_frames[signature(layer)]=([(int(127+100*math.sin(elapsed+i/18)),int(127+100*math.cos(elapsed+i/36)),160) for i in range(108)],now)
            preview.events.extend([((tick*17)%88,now-elapsed%1.2),(((tick-1)*17)%88,now-elapsed%1.2-1.2)])
            frames[identifier]=preview.frame(elapsed) or [(0,0,0)]*108
        return frames

    def info(self):
        with self.lock:
            return dict(version=__version__,settings=self.snapshot(),effects=list(MODES),device=dict(id=ciy_x77.ID,name=ciy_x77.NAME,firmware=ciy_x77.FIRMWARE,keys=ciy_x77.KEYS),
                        status=self.status,connected=self.connected,fps=round(self.fps,1),demo=self.demo,notice=self.notice,
                        capabilities=self.capabilities,onboard=self.onboard_status,
                        presets=json.loads(json.dumps(self.presets)),library=self.library(),studio_types=studio.TYPES,workspace=json.loads(json.dumps(self.workspace)))

    def live(self):
        with self.lock:return dict(pixels=self.preview,status=self.status,connected=self.connected,fps=round(self.fps,1),mode=self.state.mode,onboard=self.onboard_status,capabilities=self.capabilities,audio=self.state.audio_status,screen=self.state.screen_status)

    def device_request(self,action,data):
        if action not in ('read','write','effect','preset'):raise ValueError('Unknown device command')
        if not isinstance(data,dict):raise ValueError('Expected device settings object')
        if not self.connected or not self.capabilities:raise ValueError('These controls need SMK firmware 2.0 and a connected keyboard')
        future=Future();self.jobs.put((future,action,data))
        try:return future.result(timeout=30)
        except TimeoutError:
            future.cancel();raise

    def device_job(self,transport,action,data):
        control=transport.control
        if not control:raise ValueError('Firmware does not support device configuration')
        if action in ('effect','preset'):
            index=onboard.integer(data.get('index'),0,9 if action=='effect' else 4)
            self.patch({'mode':3});control.command(7 if action=='effect' else 8,data=bytes((index,)))
            self.log.logger.info('Onboard %s selected: %s',action,index)
            return {'ok':True}
        raw=control.read();snapshot=onboard.decode(raw)
        if action=='write':
            if data.get('reset_lighting') and control.capabilities['version']=='2.0':raise ValueError('Lighting reset requires firmware 2.1')
            if type(data.get('reset_lighting',False)) is not bool or type(data.get('reset_all',False)) is not bool:raise ValueError('Invalid reset scope')
            updated=onboard.encode(data,raw)
            backup=self.data_dir/'keyboard-backups';backup.mkdir(exist_ok=True)
            atomic_json(backup/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json'),snapshot)
            control.write(updated);snapshot=onboard.decode(updated)
            if data.get('reset_lighting'):
                control.command(12,data=bytes((int(data.get('reset_all',False)),)));self.patch({'mode':3})
            self.log.logger.info('Keyboard configuration saved and readback verified')
        snapshot['defaults']=dict(presets=onboard.default_presets(),palette=onboard.PALETTE)
        if control.capabilities['version']!='2.0':
            snapshot['fn_bindings']=[onboard.fn_description(int.from_bytes(control.command(10,cell)[:2],'little')) for cell in range(108)]
        self.claim_requested=self.state.mode!=3
        return snapshot

    def diagnostics(self):
        with self.lock:
            return dict(pid=os.getpid(),status=self.status,connected=self.connected,
                        fps=round(self.fps,1),demo=self.demo,log_file=str(self.log.path),
                        entries=self.log.snapshot())

    def start(self):
        self.worker=threading.Thread(target=self.run,name='lighting',daemon=True);self.worker.start()
        if not self.demo:
            self.audio.start();self.screen.start()
            threading.Thread(target=self.run_keys,name='reactive-input',daemon=True).start()

    def run_keys(self):
        try:monitor_keys(self.state,self.stop)
        except Exception:
            self.log.logger.exception('Reactive input monitoring stopped')
            with self.lock:self.notice='Reactive input monitoring stopped. See Logs for details.'

    def run(self):
        transport=None;timer=None;previous=None;retry=0;start=time.monotonic();timing=FrameTiming();last_error=None;poll=0
        try:
            timer=FrameTimer()
            while not self.stop.is_set():
                began=time.monotonic()
                if transport is None and not self.demo and began>=retry:
                    retry=began+2
                    try:
                        try:
                            old=socket.create_connection(('127.0.0.1',6743),timeout=.15)
                        except OSError:old=None
                        if old is not None:
                            old.close();raise RuntimeError('Close the old SMK bridge to connect')
                        transport=ciy_x77.open_device()
                        with self.lock:self.connected=True;self.status='Connected'
                        self.log.logger.info('Lighting device connected with exclusive access')
                        self.capabilities=transport.control.capabilities if transport.control else None
                        self.claim_requested=self.state.mode!=3
                        last_error=None
                        timing.clear();previous=None
                    except (OSError,RuntimeError) as exc:
                        if str(exc)!=last_error:self.log.logger.warning('Connection unavailable: %s',exc);last_error=str(exc)
                        with self.lock:self.status=str(exc);self.connected=False
                if transport:
                    while not self.jobs.empty():
                        future,action,data=self.jobs.get_nowait()
                        if not future.set_running_or_notify_cancel():continue
                        try:future.set_result(self.device_job(transport,action,data))
                        except Exception as exc:
                            self.log.logger.exception('Device configuration command failed')
                            future.set_exception(exc)
                    if transport.control:
                        try:
                            if self.claim_requested:
                                self.claim_requested=False
                                try:transport.control.command(9)
                                except RuntimeError:
                                    self.patch({'mode':3})
                                    raise
                            if began>=poll:
                                poll=began+1;status=transport.control.command(6)
                                self.onboard_status=dict(saving=bool(status[0]),editing=bool(status[1]&128),effect=status[1]&15,save_failed=bool(status[2]&1),windows_locked=bool(status[2]&8))
                                if status[2]&4:self.patch({'mode':self.last_direct_mode})
                                elif status[2]&2 and self.state.mode!=3:self.patch({'mode':3})
                        except OSError as exc:
                            self.log.logger.warning('Device disconnected during status read: %s',exc)
                            try:transport.close()
                            except (OSError,RuntimeError):pass
                            transport=None;retry=time.monotonic()+2
                            with self.lock:
                                self.connected=False;self.fps=0;self.capabilities=None;self.onboard_status={}
                                self.status='Reconnecting: '+str(exc)
                        except RuntimeError as exc:
                            self.log.logger.warning('Device status: %s',exc)
                frame=self.state.frame(began-start)
                with self.lock:self.preview=frame if frame is not None else [(0,0,0)]*108
                if transport:
                    try:
                        transfer=time.monotonic()
                        if frame is not None or previous is not None:transport.send(frame)
                        if frame is not None:
                            timing.add(began,time.monotonic()-transfer);summary=timing.summary(30)
                            if summary:
                                with self.lock:self.fps=summary['measured_submission_fps']
                        else:
                            timing.clear()
                            with self.lock:self.fps=0
                    except (OSError,RuntimeError) as exc:
                        self.log.logger.exception('Lighting transfer failed')
                        try:transport.close()
                        except (OSError,RuntimeError):pass
                        transport=None;retry=time.monotonic()+2
                        with self.lock:
                            self.connected=False;self.fps=0;self.capabilities=None;self.onboard_status={}
                            self.status='Reconnecting: '+str(exc)
                previous=frame
                try:self.state.save_settings()
                except OSError as exc:
                    self.log.logger.error('Settings save failed: %s',exc)
                    with self.lock:self.notice='Settings could not be saved: '+str(exc)
                timer.wait(max(.001,1/30-(time.monotonic()-began)))
        except Exception as exc:
            self.log.logger.exception('Lighting worker stopped')
            with self.lock:self.status='Lighting stopped: '+str(exc);self.connected=False
        finally:
            while not self.jobs.empty():
                future,_,_=self.jobs.get_nowait()
                if not future.done():future.set_exception(RuntimeError('Keyboard disconnected'))
            if timer:timer.close()
            if transport:
                try:transport.close()
                except OSError:pass
            try:self.state.save_settings(force=True)
            except OSError:pass

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=35)
        self.audio.join();self.screen.join()
        self.state.save_settings(force=True)
        self.log.finish()
