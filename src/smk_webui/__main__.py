"""SMK WebUI desktop entry point."""
import argparse
import json
import shutil
import threading
from pathlib import Path
import urllib.request
import webbrowser

from .application import Application
from .server import Server
from .settings import validate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--background',action='store_true')
    parser.add_argument('--demo',action='store_true',help='Preview without keyboard access')
    parser.add_argument('--no-tray',action='store_true')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[2]/'data')
    parser.add_argument('--import-settings',type=Path)
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Invalid port')
    url=f'http://127.0.0.1:{args.port}'
    try:server=Server(('127.0.0.1',args.port),None)
    except OSError:
        try:
            with urllib.request.urlopen(url+'/api/session',timeout=2) as response:existing=json.load(response)
            if existing.get('app')!='SMK WebUI':raise RuntimeError('Port is used by another application')
            if not args.background:webbrowser.open(url)
            return
        except Exception as exc:raise RuntimeError('Could not start or find SMK WebUI on its local port') from exc
    if args.import_settings and args.import_settings.exists() and not (args.data_dir/'settings.json').exists():
        validate(json.loads(args.import_settings.read_text()))
        args.data_dir.mkdir(parents=True,exist_ok=True);shutil.copyfile(args.import_settings,args.data_dir/'settings.json')
    app=Application(args.data_dir,args.demo);server.app=app
    if args.demo and not (args.data_dir/'settings.json').exists():app.patch({'mode':4})
    threading.Thread(target=server.serve_forever,daemon=True).start();app.start()
    print('SMK WebUI: '+url,flush=True)
    if not args.background:webbrowser.open(url)
    try:
        if not args.no_tray:
            from .tray import run_tray
            try:run_tray(app,url)
            except (OSError,RuntimeError) as exc:
                app.log.logger.warning('Tray unavailable: %s',exc)
                app.notice=f'Tray icon unavailable: {exc}. Use Quit lighting app in the browser to exit.'
                app.stop.wait()
        else:app.stop.wait()
    except KeyboardInterrupt:pass
    finally:app.close();server.shutdown();server.server_close()


if __name__=='__main__':main()
