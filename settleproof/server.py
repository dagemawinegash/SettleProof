"""Local browser API. Bind to loopback; public deployment is a separate phase."""
from dataclasses import asdict
import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .inputs import Inputs, InputError, MAX_BYTES
from .jobs import RunService, BusyError, read_json

WEB=Path(__file__).with_name('web')


def create_app(settings=None, *, root=None, service=None):
    root=Path(root or Path.cwd())
    settings=settings or Settings.load()
    service=service or RunService(settings,root)
    app=FastAPI(title='SettleProof',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.runs=service
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

    @app.middleware('http')
    async def boundary(request:Request,call_next):
        if request.method=='POST' and request.url.path.startswith('/api/'):
            if request.headers.get('X-SettleProof')!='1':
                return JSONResponse({'detail':'Same-origin application request required'},status_code=403)
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Cross-origin requests are not accepted'},status_code=403)
            length=request.headers.get('content-length')
            if not length or not length.isdigit():
                return JSONResponse({'detail':'A bounded request body is required'},status_code=411)
            if int(length)>600_000:
                return JSONResponse({'detail':'Files exceed the upload limit'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(FileNotFoundError)
    async def missing(request,exc):
        return JSONResponse({'detail':'Run or artifact not found'},status_code=404)

    @app.exception_handler(InputError)
    async def invalid(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=422)

    @app.exception_handler(BusyError)
    async def busy(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=409)

    async def files(payments,bank):
        try:
            p=await payments.read(MAX_BYTES+1)
            b=await bank.read(MAX_BYTES+1)
        finally:
            await payments.close(); await bank.close()
        if len(p)>MAX_BYTES or len(b)>MAX_BYTES:
            raise HTTPException(413,'Each file must be at most 256,000 bytes')
        inputs=Inputs.from_bytes(p,b)
        return p,b,inputs

    @app.get('/api/health')
    def health():
        return {'ok':True,'model':settings.model,'currency':'USD','max_bytes':MAX_BYTES,'max_rows':200}

    @app.get('/api/runs')
    def history():
        return service.history()

    @app.post('/api/validate')
    async def validate(payments:UploadFile=File(),bank:UploadFile=File()):
        p,b,inputs=await files(payments,bank)
        return {'valid':True,'currency':'USD','payments':len(inputs.payments),'bank':len(inputs.bank),
                'source_sha256':inputs.hashes}

    @app.post('/api/runs',status_code=202)
    async def start(payments:UploadFile=File(),bank:UploadFile=File()):
        def name(value,fallback):
            return ''.join(c for c in (value or fallback).replace('\\','/').rsplit('/',1)[-1] if c.isprintable())[:80]
        names={'payments':name(payments.filename,'payments.csv'),'bank':name(bank.filename,'bank.csv')}
        p,b,inputs=await files(payments,bank)
        return {'run_id':service.start(p,b,names)}

    @app.get('/api/runs/{run_id}')
    def snapshot(run_id:str):
        return service.snapshot(run_id)

    @app.get('/api/runs/{run_id}/report')
    def report(run_id:str):
        run=service.snapshot(run_id)
        if not run['report_available']:
            raise HTTPException(409,'A checked report is not yet available')
        return read_json(service.path(run_id)/'report.json')

    @app.post('/api/runs/{run_id}/cancel')
    def cancel(run_id:str):
        service.snapshot(run_id)
        return {'requested':service.cancel(run_id),'message':'Cancellation takes effect at the next safe checkpoint; cleanup follows.'}

    @app.get('/api/runs/{run_id}/attempts')
    def attempts(run_id:str):
        run=service.snapshot(run_id)
        folder=service.path(run_id)
        result=[]
        for number in range(1,4):
            attempt=folder/f'attempt-{number:02}'
            if not attempt.is_dir():
                continue
            source=attempt/'program.py'
            checker=read_json(attempt/'checker.json',{})
            result.append({'number':number,'code':source.read_text(encoding='utf-8') if source.is_file() else '',
                'model':read_json(attempt/'model.json',{}),'execution':read_json(attempt/'execution.json',{}),
                'checker':checker,'status':'accepted' if checker.get('accepted') else 'rejected' if checker.get('accepted') is False else 'pending'})
        return {'run_id':run_id,'attempts':result,'replay_verified':run.get('replay_verified',False),
                'sandbox_id':run.get('sandbox_id'),'sandbox_cleanup':run.get('sandbox_cleanup')}

    @app.get('/api/runs/{run_id}/download/{artifact}')
    def download(run_id:str,artifact:str):
        run=service.snapshot(run_id)
        choices={'report.csv':('report.csv','text/csv'),'report.json':('report.json','application/json'),
                 'program.py':('program.py','text/plain'),'payments.csv':('inputs/payments.csv','text/csv'),
                 'bank.csv':('inputs/bank.csv','text/csv')}
        if artifact not in choices:
            raise FileNotFoundError()
        if artifact in ('report.csv','report.json','program.py') and not run['report_available']:
            raise HTTPException(409,'Only accepted results can be exported')
        relative,media=choices[artifact]
        path=service.path(run_id)/relative
        if not path.is_file():
            raise FileNotFoundError()
        return FileResponse(path,media_type=media,filename=run_id+'-'+artifact)

    @app.get('/api/samples/{kind}')
    def sample(kind:str):
        if kind not in ('payments','bank'):
            raise FileNotFoundError()
        path=root/'fixtures'/'demo'/f'{kind}.csv'
        return FileResponse(path,media_type='text/csv',filename=f'sample-{kind}.csv')

    @app.get('/')
    def index():
        return FileResponse(WEB/'index.html',media_type='text/html')

    if WEB.is_dir():
        app.mount('/static',StaticFiles(directory=WEB),name='static')
    return app
