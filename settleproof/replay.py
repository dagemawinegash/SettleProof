"""Replay a saved accepted program remotely, without calling the model."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from .agent import active_run, now, write_json
from .checker import check, CheckError
from .createos import CreateOS
from .inputs import Inputs


def replay_saved(settings, folder, *, sandbox=None):
    folder=Path(folder)
    manifest=json.loads((folder/'run.json').read_text(encoding='utf-8'))
    if manifest.get('status')!='checked' or not manifest.get('replay_verified'):
        raise ValueError('Only an accepted run with a verified original replay can be replayed')
    inputs=Inputs.load(folder/'inputs'/'payments.csv',folder/'inputs'/'bank.csv')
    code=(folder/'program.py').read_bytes()
    digest=hashlib.sha256(code).hexdigest()
    if inputs.hashes!=manifest.get('source_sha256'):
        raise ValueError('Saved inputs no longer match the accepted run')
    if not manifest.get('program_sha256') or digest!=manifest['program_sha256']:
        raise ValueError('Saved program is missing its accepted source hash or has changed')
    expected=json.loads((folder/'report.json').read_text(encoding='utf-8'))
    client=sandbox or CreateOS(settings)
    sandbox_id=None
    result={'started_at':now(),'status':'starting','source_sha256':inputs.hashes,
            'program_sha256':digest,'model_called':False,'sandbox_id':None}
    path=folder/'replays'/('replay-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json')
    with active_run(Path('.local')):
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            sandbox_id=client.create('sp-replay-'+uuid.uuid4().hex[:8])
            result['sandbox_id']=sandbox_id
            write_json(path,result)
            client.ready(sandbox_id)
            result['sandbox_policy']=client.prepare(sandbox_id,inputs)
            execution=client.run(sandbox_id,code.decode('utf-8'),inputs)
            result['execution']=execution
            if execution.get('exit_code')!=0 or execution.get('timed_out') or execution.get('output_truncated'):
                raise CheckError('Saved program failed during remote replay')
            candidate=json.loads(execution['stdout'])
            report=check(candidate,inputs)
            if report!=expected:
                raise CheckError('Saved program replay differs from the accepted evidence report')
            result['status']='checked'
        except KeyboardInterrupt:
            result['status']='cancelled'
            raise
        except Exception:
            result['status']='failed'
            raise
        finally:
            if sandbox_id:
                try:
                    client.delete(sandbox_id)
                    result['sandbox_cleanup']='deleted'
                except Exception:
                    result['sandbox_cleanup']='delete_failed'
            result['finished_at']=now()
            write_json(path,result)
    return path,result
