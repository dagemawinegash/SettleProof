"""This harness runs IN THE UNTRUSTED VM. Its output is independently checked.

No controller secrets enter this process. This is resource management, not an
in-process security boundary; CreateOS is the boundary for generated code.
"""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile


def limits():
    resource.setrlimit(resource.RLIMIT_CPU,(20,20))
    resource.setrlimit(resource.RLIMIT_AS,(384*1024*1024,384*1024*1024))
    resource.setrlimit(resource.RLIMIT_FSIZE,(512*1024,512*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))


with tempfile.TemporaryDirectory(prefix='settleproof-') as folder:
    with open(Path(folder)/'stdout','w+b') as out, open(Path(folder)/'stderr','w+b') as err:
        process=subprocess.Popen([sys.executable,'-I','/workspace/program.py',
            '/workspace/payments.csv','/workspace/bank.csv'], cwd=folder,
            env={'PATH':'/usr/bin:/bin','HOME':folder,'PYTHONHASHSEED':'0'},
            stdout=out,stderr=err,start_new_session=True,preexec_fn=limits)
        timed_out=False
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            timed_out=True
        finally:
            # Terminate surviving children too, including after a normal parent exit.
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        out.seek(0); err.seek(0)
        stdout=out.read(262145); stderr=err.read(8193)
        print(json.dumps({'exit_code':process.returncode,'timed_out':timed_out,
            'output_truncated':len(stdout)>262144 or len(stderr)>8192,
            'stdout':stdout[:262144].decode('utf-8',errors='replace'),
            'stderr':stderr[:8192].decode('utf-8',errors='replace')}))
