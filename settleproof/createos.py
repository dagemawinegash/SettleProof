import json
from pathlib import Path
import time
from urllib.parse import quote

from .http import Http, ServiceError


# Empty egress means OPEN access in CreateOS. A nonempty allowlist restricts it.
# This TEST-NET address is the only permitted target; no model/API endpoint is allowed.
EGRESS = ['203.0.113.1:1']


class CreateOS:
    def __init__(self, settings):
        self.http=Http(settings.createos_base, {'X-Api-Key':settings.createos_key})

    def call(self, method, path, body=None, **kwargs):
        payload=self.http.request(method,path,body,**kwargs)
        if payload.get('status')!='success':
            raise ServiceError('CreateOS returned an unsuccessful response')
        return payload.get('data',{})

    def identity(self):
        return self.call('GET','/v1/whoami')

    def create(self, name):
        data=self.call('POST','/v1/sandboxes',{
            'name':name,'shape':'s-1vcpu-1gb','rootfs':'devbox:1',
            'ingress_enabled':False,'egress':EGRESS,'auto_pause_after_seconds':600},timeout=120)
        sandbox_id=data.get('id')
        if not isinstance(sandbox_id,str) or not sandbox_id:
            raise ServiceError('CreateOS creation response did not include a sandbox ID')
        return sandbox_id

    def ready(self, sandbox_id):
        deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            data=self.call('GET',f'/v1/sandboxes/{sandbox_id}')
            state=data.get('status') or data.get('state')
            if state=='running':
                return data
            if state in ('error','failed','deleted','destroyed','stopped'):
                raise ServiceError(f'CreateOS sandbox entered state {state}')
            time.sleep(2)
        raise ServiceError('CreateOS sandbox did not become ready within 150 seconds')

    def put(self, sandbox_id, name, content):
        self.http.request('PUT',f'/v1/sandboxes/{sandbox_id}/files?path='+quote('/workspace/'+name,safe=''),content)

    def get(self, sandbox_id, name):
        return self.http.request('GET',f'/v1/sandboxes/{sandbox_id}/files?path='+quote('/workspace/'+name,safe=''),raw=True)

    def exec(self, sandbox_id, cmd, args):
        data=self.call('POST',f'/v1/sandboxes/{sandbox_id}/exec',{'cmd':cmd,'args':args},timeout=60)
        result=data.get('result')
        if not isinstance(result,dict) or type(result.get('exit_code')) is not int:
            raise ServiceError('CreateOS returned an invalid execution result')
        return result

    def prepare(self, sandbox_id, inputs):
        self.put(sandbox_id,'payments.csv',inputs.payment_bytes)
        self.put(sandbox_id,'bank.csv',inputs.bank_bytes)
        self.put(sandbox_id,'runner.py',Path(__file__).with_name('sandbox_runner.py').read_bytes())
        # Probe an external destination that is outside the configured allowlist.
        script='''import json,socket,sys
try:
 s=socket.create_connection(("1.1.1.1",443),timeout=3); s.close()
 print(json.dumps({"outside_allowlist_connection":"allowed"})); sys.exit(1)
except OSError:
 print(json.dumps({"outside_allowlist_connection":"blocked","tested_target":"1.1.1.1:443"}))
'''
        probe=self.exec(sandbox_id,'/usr/bin/python3',['-I','-c',script])
        if probe['exit_code']!=0:
            raise ServiceError('External connection probe succeeded despite the requested egress restriction')
        try:
            evidence=json.loads(probe['stdout'])
            if evidence.get('outside_allowlist_connection')!='blocked':
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise ServiceError('Could not verify network probe result') from None
        return {'egress_allowlist':EGRESS,'ingress_enabled':False,'probe':evidence,
                'limitation':'One blocked connection probe is evidence of this restriction, not a complete network-isolation audit.'}

    def run(self, sandbox_id, code, inputs):
        self.put(sandbox_id,'program.py',code.encode())
        # Restore the harness for every attempt; the VM is untrusted.
        self.put(sandbox_id,'runner.py',Path(__file__).with_name('sandbox_runner.py').read_bytes())
        self.put(sandbox_id,'payments.csv',inputs.payment_bytes)
        self.put(sandbox_id,'bank.csv',inputs.bank_bytes)
        outer=self.exec(sandbox_id,'/usr/bin/timeout',
                        ['-k','2s','40s','/usr/bin/python3','-I','/workspace/runner.py'])
        if outer['exit_code']!=0:
            return {'exit_code':outer['exit_code'],'stdout':'','stderr':outer.get('stderr','')[:8192],
                    'timed_out':outer['exit_code'] in (124,137),'output_truncated':False,'harness_failure':True}
        try:
            result=json.loads(outer['stdout'])
            if not isinstance(result,dict) or type(result.get('exit_code')) is not int:
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise ServiceError('Sandbox harness returned malformed execution evidence') from None
        if self.get(sandbox_id,'payments.csv')!=inputs.payment_bytes or self.get(sandbox_id,'bank.csv')!=inputs.bank_bytes:
            raise ServiceError('Generated program modified an input copy')
        if self.get(sandbox_id,'program.py')!=code.encode():
            raise ServiceError('Generated program changed its own source')
        return result

    def delete(self, sandbox_id):
        data=self.call('DELETE',f'/v1/sandboxes/{sandbox_id}')
        if data.get('status')=='destroyed':
            return
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            try:
                data=self.call('GET',f'/v1/sandboxes/{sandbox_id}',timeout=10)
            except ServiceError as exc:
                if exc.status==404:
                    return
                raise
            if data.get('status')=='destroyed':
                return
            time.sleep(1)
        raise ServiceError('Sandbox deletion was accepted but did not complete within 45 seconds')
