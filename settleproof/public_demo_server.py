"""Credential-free public viewer for a real saved synthetic run.

This entry point cannot execute code, accept uploads, or query private history.
The full owner workspace is served by settleproof.hosted.
"""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs


ROOT=Path(os.environ.get('SETTLEPROOF_APP_DIR', Path(__file__).resolve().parent.parent)).resolve()
WEB=ROOT/'settleproof/web'
SEED=ROOT/'public-demo'
MANIFEST=json.loads((SEED/'run.json').read_text())
RID=MANIFEST['run_id']


class Viewer(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def send(self,body,status=200,kind='application/json',download=None):
        if not isinstance(body,bytes):
            body=json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store' if kind=='application/json' else 'no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if download:
            self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.end_headers()
        if self.command!='HEAD':
            self.wfile.write(body)

    def file(self,path,download=None):
        if not path.is_file():
            return self.send({'detail':'Not found'},404)
        kind=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        return self.send(path.read_bytes(),kind=kind,download=download)

    def do_POST(self):
        self.send({'detail':'This public viewer is read-only. Run SettleProof locally for a new comparison.'},403)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed=urlsplit(self.path)
        path=unquote(parsed.path)
        if path=='/':
            return self.file(WEB/'index.html')
        if path.startswith('/static/'):
            target=(WEB/path[len('/static/'):]).resolve()
            if target.is_relative_to(WEB.resolve()):
                return self.file(target)
        if path in ('/api/health','/api/session'):
            return self.send({'ok':True,'hosted':True,'owner':False,'read_only':True,'currency':'USD','model':MANIFEST.get('model'),'max_bytes':256000,'max_rows':200})
        run={**MANIFEST,'events':[],'artifacts_available':True,'report_available':True,'data_kind':'synthetic_sample'}
        if path=='/api/runs':
            return self.send({'runs':[run],'database':'public_demo'})
        if path=='/api/runs/'+RID:
            return self.send(run)
        if path=='/api/runs/'+RID+'/report':
            return self.send(json.loads((SEED/'report.json').read_text()))
        if path=='/api/runs/'+RID+'/attempts':
            attempts=[]
            for number in range(1,4):
                folder=SEED/f'attempt-{number:02}'
                if not folder.is_dir():
                    continue
                def read(name):
                    source=folder/name
                    return json.loads(source.read_text()) if source.is_file() else {}
                checker=read('checker.json')
                attempts.append({'number':number,'code':(folder/'program.py').read_text(),
                                 'model':read('model.json'),'execution':read('execution.json'),'checker':checker,
                                 'status':'accepted' if checker.get('accepted') else 'rejected'})
            return self.send({'run_id':RID,'attempts':attempts,'replay_verified':MANIFEST.get('replay_verified',False),
                              'sandbox_id':MANIFEST.get('sandbox_id'),'sandbox_cleanup':MANIFEST.get('sandbox_cleanup')})
        prefix='/api/runs/'+RID+'/download/'
        if path.startswith(prefix):
            name=path[len(prefix):]
            choices={'report.json':'report.json','report.csv':'report.csv','program.py':'program.py',
                     'payments.csv':'inputs/payments.csv','bank.csv':'inputs/bank.csv'}
            if name in choices:
                return self.file(SEED/choices[name],download=name)
        if path.startswith('/api/samples/'):
            kind=path.rsplit('/',1)[-1]
            profile=parse_qs(parsed.query).get('profile',['standard'])[0]
            if kind in ('payments','bank') and profile in ('standard','renamed'):
                return self.file(ROOT/'fixtures'/('demo' if profile=='standard' else 'alternate')/(kind+'.csv'),download=kind+'.csv')
        self.send({'detail':'Not found'},404)


if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Viewer).serve_forever()
