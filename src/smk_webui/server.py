"""Loopback-only WebUI API."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import socket
from . import startup,screen
from urllib.parse import urlsplit

WEB=Path(__file__).with_name('web')


class Server(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()
    def __init__(self,address,app):
        super().__init__(address,Handler)
        self.app=app;self.token=secrets.token_urlsafe(32)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def safe_origin(self):
        hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        return self.headers.get('Host') in hosts and self.headers.get('Origin') in (None,*('http://'+h for h in hosts))
    def respond(self,status,value,content_type='application/json'):
        data=json.dumps(value).encode() if content_type=='application/json' else value
        self.send_response(status);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(data)
    def authorized(self):
        return self.safe_origin() and secrets.compare_digest(self.headers.get('X-SMK-Token',''),self.server.token)
    def do_GET(self):
        if not self.safe_origin():return self.respond(403,{'error':'Local access only'})
        path=urlsplit(self.path).path
        if path=='/api/session':return self.respond(200,{'app':'SMK WebUI','token':self.server.token})
        if path.startswith('/api/'):
            if not self.authorized():return self.respond(403,{'error':'Invalid session'})
            if path=='/api/screens':
                try:return self.respond(200,{'monitors':screen.monitors()})
                except (OSError,AttributeError):return self.respond(200,{'monitors':[],'error':'Display enumeration unavailable'})
            if path=='/api/startup':return self.respond(200,startup.status())
            if path=='/api/state':return self.respond(200,self.server.app.info())
            if path=='/api/library':return self.respond(200,self.server.app.export_library())
            if path=='/api/live':return self.respond(200,self.server.app.live())
            if path=='/api/logs':return self.respond(200,self.server.app.diagnostics())
            if path.startswith('/api/presets/'):
                identifier=path.rsplit('/',1)[-1]
                with self.server.app.lock:
                    item=next((p for p in self.server.app.presets+self.server.app.library() if p['id']==identifier),None)
                if item:return self.respond(200,{'format':'smk-webui-preset','version':1,'name':item['name'],'settings':item['settings']})
            return self.respond(404,{'error':'Not found'})
        assets={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/studio.js':'studio.js','/screen.js':'screen.js','/controls.js':'controls.js','/style.css':'style.css','/icon.svg':'icon.svg','/icon.ico':'icon.ico','/logo.png':'logo.png'}
        if path not in assets:return self.respond(404,{'error':'Not found'})
        file=WEB/assets[path]
        self.respond(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
    def do_POST(self):
        if not self.authorized():return self.respond(403,{'error':'Invalid session'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            limit=4194304 if urlsplit(self.path).path=='/api/presets/import-library' else 262144
            if not 0<length<=limit:raise ValueError('Request is too large or empty')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Expected JSON')
            data=json.loads(self.rfile.read(length));path=urlsplit(self.path).path
            if path=='/api/screens':
                try:return self.respond(200,{'monitors':screen.monitors()})
                except (OSError,AttributeError):return self.respond(200,{'monitors':[],'error':'Display enumeration unavailable'})
            if path=='/api/startup':return self.respond(200,startup.set_enabled(data.get('enabled')))
            if path=='/api/previews':return self.respond(200,self.server.app.previews(data))
            if path=='/api/settings':return self.respond(200,self.server.app.patch(data))
            if path=='/api/settings/restore':return self.respond(200,self.server.app.restore(data))
            if path=='/api/solo':return self.respond(200,self.server.app.solo(data))
            if path=='/api/workspace':return self.respond(200,self.server.app.save_workspace(data))
            if path.startswith('/api/device/'):
                return self.respond(200,self.server.app.device_request(path.rsplit('/',1)[-1],data))
            if path.startswith('/api/presets/'):
                return self.respond(200,self.server.app.preset(path.rsplit('/',1)[-1],data))
            if path=='/api/quit':
                self.respond(200,{'ok':True});self.server.app.stop.set();return
            return self.respond(404,{'error':'Not found'})
        except (ValueError,TypeError,KeyError) as exc:self.respond(400,{'error':str(exc)})
        except (RuntimeError,TimeoutError) as exc:self.respond(409,{'error':str(exc)})
        except OSError:self.respond(500,{'error':'Could not save changes. Check the data folder is writable.'})
