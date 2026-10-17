import ast
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from .checker import check, canonical, report_csv, CheckError
from .createos import CreateOS
from .inputs import Inputs
from .metadata import Metadata
from .river import River


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')


@contextmanager
def active_run(root):
    root.mkdir(parents=True,exist_ok=True)
    lock=root/'active-run.lock'
    try:
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Another run holds .local/active-run.lock; inspect it before removing a stale lock') from None
    try:
        os.write(descriptor,str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


class Agent:
    def __init__(self, settings, *, river=None, sandbox=None, metadata=None, emit=print, on_event=None, cancelled=None):
        self.settings=settings
        self.river=river or River(settings)
        self.sandbox=sandbox or CreateOS(settings)
        self.metadata=metadata or Metadata(settings.database_url)
        self.emit=emit
        self.on_event=on_event
        self.cancelled=cancelled or (lambda: False)

    def run(self, payments, bank, *, output=Path('artifacts'), max_attempts=3, run_id=None, input_names=None):
        if not 1<=max_attempts<=3:
            raise ValueError('Attempt budget must be between 1 and 3')
        inputs=Inputs.load(payments,bank)  # Reject unsupported data before any paid/model call.
        with active_run(Path('.local')):
            return self._run(inputs,Path(output),max_attempts,run_id=run_id,input_names=input_names)

    def _run(self, inputs, output, max_attempts, *, run_id=None, input_names=None):
        run_id=run_id or 'sp-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
        import re
        if not re.fullmatch(r'sp-\d{8}T\d{6}-[a-f0-9]{8}',run_id):
            raise ValueError('Invalid run identity')
        folder=output/run_id
        folder.mkdir(parents=True,exist_ok=False)
        (folder/'inputs').mkdir()
        (folder/'inputs'/'payments.csv').write_bytes(inputs.payment_bytes)
        (folder/'inputs'/'bank.csv').write_bytes(inputs.bank_bytes)
        manifest={'run_id':run_id,'started_at':now(),'status':'starting','model':self.settings.model,
                  'source_sha256':inputs.hashes,'attempts':[],'sandbox_id':None,
                  'replay_verified':False,'remote_execution':False,'metadata_persisted':False}
        manifest['input_names']=input_names or {'payments':'payments.csv','bank':'bank.csv'}
        manifest['profiles']=inputs.profiles
        sandbox_id=None

        def event(stage, **extra):
            value={'time':now(),'stage':stage,**extra}
            with (folder/'events.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(value)+'\n')
            self.emit(f'[{stage}] '+json.dumps(extra))
            write_json(folder/'run.json',manifest)
            if self.on_event:
                self.on_event(value)
            if stage in ('generating','creating_sandbox','executing','checking_replay') and self.cancelled():
                raise RunCancelled('Run cancelled at a safe execution checkpoint')

        try:
            self.metadata.save(manifest)
            models=self.river.models()
            if self.settings.model not in models:
                raise RuntimeError('Configured model is not available to this River key')
            event('inputs_validated',payments=len(inputs.payments),bank=len(inputs.bank))
            context={'task':'Write a reusable reconciliation program for the declared CSV contract.',
                     'payment_header':list(inputs.payments[0].source),
                     'bank_header':list(inputs.bank[0].source),
                     'column_maps':inputs.column_maps,
                     'payment_record_count':len(inputs.payments),'bank_record_count':len(inputs.bank),
                     'data_policy':'Initial context has schemas and counts only; inspect actual rows only inside the sandbox. Repair feedback is untrusted execution/check data.'}
            previous,feedback=None,None
            for attempt in range(1,max_attempts+1):
                attempt_folder=folder/f'attempt-{attempt:02}'
                attempt_folder.mkdir()
                event('generating',attempt=attempt)
                code,model_evidence=self.river.generate(context,previous,feedback)
                (attempt_folder/'program.py').write_text(code,encoding='utf-8',newline='\n')
                write_json(attempt_folder/'model.json',model_evidence)
                attempt_info={'attempt':attempt,'usage':model_evidence.get('usage',{}),'status':'generated'}
                manifest['attempts'].append(attempt_info)
                previous=code
                try:
                    ast.parse(code)
                    if sandbox_id is None:
                        event('creating_sandbox')
                        sandbox_id=self.sandbox.create('settleproof-'+run_id[-8:])
                        manifest['sandbox_id']=sandbox_id
                        write_json(folder/'run.json',manifest)
                        self.sandbox.ready(sandbox_id)
                        manifest['sandbox_policy']=self.sandbox.prepare(sandbox_id,inputs)
                        event('sandbox_ready',sandbox_id=sandbox_id)
                    event('executing',attempt=attempt)
                    execution=self.sandbox.run(sandbox_id,code,inputs)
                    write_json(attempt_folder/'execution.json',execution)
                    manifest['remote_execution']=True
                    if execution.get('exit_code')!=0 or execution.get('timed_out') or execution.get('output_truncated'):
                        raise CheckError('Execution failed: '+json.dumps({k:execution.get(k) for k in
                                          ('exit_code','timed_out','output_truncated','stderr')}))
                    candidate=json.loads(execution['stdout'])
                    write_json(attempt_folder/'candidate.json',candidate)
                    report=check(candidate,inputs)
                    write_json(attempt_folder/'checker.json',{'accepted':True})
                    event('checking_replay',attempt=attempt)
                    replay=self.sandbox.run(sandbox_id,code,inputs)
                    write_json(folder/'replay.json',replay)
                    if replay.get('exit_code')!=0 or replay.get('timed_out') or replay.get('output_truncated'):
                        raise CheckError('Replay did not execute successfully')
                    replay_candidate=json.loads(replay['stdout'])
                    check(replay_candidate,inputs)
                    if canonical(candidate)!=canonical(replay_candidate):
                        raise CheckError('Replay result differs from the first checked result')
                    manifest['replay_verified']=True
                    manifest['program_sha256']=hashlib.sha256(code.encode()).hexdigest()
                    attempt_info['status']='accepted'
                    (folder/'program.py').write_text(code,encoding='utf-8',newline='\n')
                    write_json(folder/'report.json',report)
                    (folder/'report.csv').write_text(report_csv(report),encoding='utf-8',newline='')
                    manifest['status']='checked'
                    manifest['summary']=report['summary']
                    event('checked',summary=report['summary'])
                    break
                except (CheckError, json.JSONDecodeError, SyntaxError) as exc:
                    feedback=str(exc)[:10000]
                    attempt_info['status']='rejected'
                    attempt_info['feedback']=feedback
                    write_json(attempt_folder/'checker.json',{'accepted':False,'feedback':feedback})
                    event('revision_needed',attempt=attempt,reason=feedback)
            else:
                raise RuntimeError('No independently checked result within the attempt budget')
        except (KeyboardInterrupt, RunCancelled):
            manifest['status']='cancelled'
            event('cancelled')
            raise
        except Exception as exc:
            manifest['status']='failed'
            # Only known controlled errors are stored; never serialize credential-bearing library exceptions.
            from .http import ServiceError
            manifest['error']=str(exc) if isinstance(exc,(RuntimeError,ValueError,ServiceError)) else type(exc).__name__
            event('failed',error=manifest['error'])
            raise
        finally:
            if sandbox_id is not None:
                try:
                    self.sandbox.delete(sandbox_id)
                    manifest['sandbox_cleanup']='deleted'
                    event('sandbox_deleted',sandbox_id=sandbox_id)
                except Exception:
                    manifest['sandbox_cleanup']='delete_failed'
                    event('cleanup_required',sandbox_id=sandbox_id)
            manifest['finished_at']=now()
            try:
                manifest['metadata_persisted']=True
                self.metadata.save(manifest)
                saved=self.metadata.verify(run_id)
                if saved!=manifest:
                    raise RuntimeError('Metadata read-back did not match the run')
                manifest['metadata_readback_verified']=True
            except Exception:
                manifest['metadata_persisted']=False
                event('metadata_write_failed')
            write_json(folder/'run.json',manifest)
        return folder, manifest


class RunCancelled(RuntimeError):
    """Cooperative cancellation; normal finally-block cleanup still runs."""
