"""Single-user local job service. No generated code runs in this process."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import uuid

from .agent import Agent, RunCancelled
from .inputs import Inputs
from .metadata import Metadata

RUN_ID=re.compile(r'sp-\d{8}T\d{6}-[a-f0-9]{8}\Z')


class BusyError(RuntimeError):
    pass


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return default


@dataclass
class Job:
    run_id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    error: str | None = None
    events: list = field(default_factory=list)


class RunService:
    def __init__(self, settings, root, *, agent_factory=Agent):
        self.settings=settings
        self.root=Path(root)
        self.artifacts=self.root/'artifacts'
        self.uploads=self.root/'uploads'
        self.metadata=Metadata(settings.database_url)
        self.agent_factory=agent_factory
        self.jobs={}
        self.lock=threading.Lock()
        self.active=None

    def path(self, run_id):
        if not RUN_ID.fullmatch(run_id):
            raise FileNotFoundError('Run not found')
        return self.artifacts/run_id

    def start(self, payments, bank, names):
        Inputs.from_bytes(payments,bank)
        with self.lock:
            if self.active and self.jobs[self.active].thread.is_alive():
                raise BusyError('A reconciliation is already running. Wait for it to finish or request cancellation.')
            if (self.root/'.local'/'active-run.lock').exists():
                raise BusyError('Another controller run holds the workspace lock. Wait for it to finish.')
            run_id='sp-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
            job=Job(run_id)
            folder=self.uploads/run_id
            folder.mkdir(parents=True,exist_ok=False)
            (folder/'payments.csv').write_bytes(payments)
            (folder/'bank.csv').write_bytes(bank)
            def record(event):
                with self.lock:
                    job.events.append(event)
            def work():
                try:
                    agent=self.agent_factory(self.settings,emit=lambda _:None,on_event=record,cancelled=job.cancel.is_set)
                    agent.run(folder/'payments.csv',folder/'bank.csv',output=self.artifacts,
                              run_id=run_id,input_names=names)
                except RunCancelled:
                    job.error='Cancelled at a safe checkpoint. Any created sandbox is cleaned up by the controller.'
                except Exception as exc:
                    job.error=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'The run stopped unexpectedly. Inspect its execution evidence.'
                finally:
                    # Remove only the two temporary uploads created by this job.
                    for name in ('payments.csv','bank.csv'):
                        (folder/name).unlink(missing_ok=True)
                    try:
                        folder.rmdir()
                    except OSError:
                        pass
            job.thread=threading.Thread(target=work,name=run_id,daemon=True)
            self.jobs[run_id]=job
            self.active=run_id
            job.thread.start()
            return run_id

    def snapshot(self, run_id):
        folder=self.path(run_id)
        manifest=read_json(folder/'run.json',{})
        with self.lock:
            job=self.jobs.get(run_id)
            active=bool(job and job.thread.is_alive())
            events=list(job.events) if job else []
        if not manifest and not job:
            raise FileNotFoundError('Run not found')
        if not events:
            try:
                events=[json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines() if line]
            except (OSError,ValueError):
                events=[]
        status='cancelling' if active and job.cancel.is_set() else 'running' if active else manifest.get('status','failed')
        if not active and status in ('starting','generated'):
            status='interrupted'
        return {**manifest,'run_id':run_id,'status':status,'events':events,
                'error':manifest.get('error') or (job.error if job else None),
                'artifacts_available':folder.is_dir(),
                'report_available':not active and status=='checked' and (folder/'report.json').is_file()}

    def cancel(self, run_id):
        with self.lock:
            job=self.jobs.get(run_id)
            if not job or not job.thread.is_alive():
                return False
            job.cancel.set()
            return True

    def local_history(self):
        if not self.artifacts.exists():
            return []
        result=[]
        for folder in self.artifacts.iterdir():
            if folder.is_dir() and RUN_ID.fullmatch(folder.name):
                try:
                    result.append(self.snapshot(folder.name))
                except FileNotFoundError:
                    pass
        return sorted(result,key=lambda r:r.get('started_at',r['run_id']),reverse=True)

    def history(self):
        return {'runs':self.local_history(),'database':'not_loaded'}
