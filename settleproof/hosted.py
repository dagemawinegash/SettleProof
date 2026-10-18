"""Hosted single-owner workspace with a public, immutable synthetic demonstration."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import Settings
from .server import create_app


def protect(app, access_code, public_run_id, *, secure=True):
    if len(access_code) < 20:
        raise ValueError('Hosted owner access code must have at least 20 characters')
    token = hmac.new(access_code.encode(), secrets.token_bytes(32), hashlib.sha256).hexdigest()
    failures = {}

    def authenticated(request):
        return hmac.compare_digest(request.cookies.get('settleproof_owner', ''), token)

    @app.middleware('http')
    async def hosted_boundary(request: Request, call_next):
        path = request.url.path
        owner = authenticated(request)
        if path == '/api/session' and request.method == 'GET':
            return JSONResponse({'hosted': True, 'owner': owner}, headers={'Cache-Control':'no-store'})
        if path == '/api/session' and request.method == 'POST':
            # Same-origin protection is explicit here because this middleware returns directly.
            origin = request.headers.get('origin')
            length = request.headers.get('content-length', '')
            if request.headers.get('X-SettleProof') != '1' or (origin and origin.rstrip('/') != str(request.base_url).rstrip('/')):
                return JSONResponse({'detail':'Same-origin request required'}, status_code=403)
            if not length.isdigit() or int(length) > 1024:
                return JSONResponse({'detail':'Invalid login request'}, status_code=413)
            address = request.client.host if request.client else 'unknown'
            now = time.monotonic()
            failures.update({key:[stamp for stamp in stamps if now-stamp < 600] for key,stamps in list(failures.items())})
            if len(failures.get(address, [])) >= 5:
                return JSONResponse({'detail':'Too many attempts. Try again in ten minutes.'}, status_code=429)
            try:
                code = (await request.json()).get('code', '')
            except (ValueError, AttributeError):
                code = ''
            if not isinstance(code, str) or not hmac.compare_digest(code.encode(), access_code.encode()):
                if len(failures) >= 512 and address not in failures:
                    return JSONResponse({'detail':'Please try again later.'}, status_code=429)
                failures.setdefault(address, []).append(now)
                return JSONResponse({'detail':'Access code was not accepted'}, status_code=401)
            failures.pop(address, None)
            response = JSONResponse({'owner':True}, headers={'Cache-Control':'no-store'})
            response.set_cookie('settleproof_owner', token, httponly=True, secure=secure, samesite='strict', max_age=14400)
            return response
        if path == '/api/runs' and request.method == 'GET' and not owner:
            run = app.state.runs.snapshot(public_run_id)
            return JSONResponse({'runs':[run], 'database':'public_demo'}, headers={'Cache-Control':'no-store'})
        if path.startswith('/api/runs') and not owner:
            allowed = request.method == 'GET' and path.startswith('/api/runs/'+public_run_id+'/')
            allowed = allowed or (request.method == 'GET' and path == '/api/runs/'+public_run_id)
            if not allowed:
                return JSONResponse({'detail':'Owner access is required for live runs and private history'}, status_code=401)
        response = await call_next(request)
        if path == '/api/health' and response.status_code == 200:
            # Health remains public and contains no credentials.
            return JSONResponse({'ok':True, 'hosted':True, 'owner':owner, 'currency':'USD',
                                 'model':app.state.runs.settings.model, 'max_bytes':256000, 'max_rows':200},
                                headers={'Cache-Control':'no-store'})
        return response
    return app


def create_hosted_app():
    source = Path(os.environ.get('SETTLEPROOF_APP_DIR', '/app')).resolve()
    root = Path(os.environ.get('SETTLEPROOF_DATA_DIR', '/app/runtime')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    if not (root/'fixtures').exists():
        shutil.copytree(source/'fixtures', root/'fixtures')
    seed = source/'public-demo'
    run_id = json.loads((seed/'run.json').read_text())['run_id']
    destination = root/'artifacts'/run_id
    if not destination.exists():
        shutil.copytree(seed, destination)
    hosts = [value.strip() for value in os.environ.get('SETTLEPROOF_ALLOWED_HOSTS', 'localhost,127.0.0.1,*.nodeops.app,*.nodeops.network').split(',') if value.strip()]
    app = create_app(Settings.load(), root=root, allowed_hosts=hosts)
    return protect(app, os.environ.get('SETTLEPROOF_OWNER_CODE', ''), run_id)
