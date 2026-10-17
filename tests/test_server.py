import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from settleproof.checker import check, report_csv
from settleproof.config import Settings
from settleproof.inputs import Inputs
from settleproof.jobs import RunService, Job
from settleproof.server import create_app
from test_checker import ROOT, demo_candidate

RID='sp-20261017T120000-1234abcd'


class StoredMetadata:
    def __init__(self, rows):self.rows=rows
    def list_recent(self):return self.rows


class BrowserApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'.local',prefix='web-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.settings=Settings('test-river-key','test-createos-key')
        self.service=RunService(self.settings,self.root)
        self.service.metadata=StoredMetadata([])
        self.client=TestClient(create_app(self.settings,root=self.root,service=self.service))
        self.p=(ROOT/'fixtures/demo/payments.csv').read_bytes()
        self.b=(ROOT/'fixtures/demo/bank.csv').read_bytes()
        self.folder=self.root/'artifacts'/RID
        (self.folder/'inputs').mkdir(parents=True)
        inputs=Inputs.from_bytes(self.p,self.b)
        report=check(demo_candidate(inputs),inputs)
        (self.folder/'run.json').write_text(json.dumps({'run_id':RID,'started_at':'2026-10-17T12:00:00+00:00',
            'finished_at':'2026-10-17T12:01:00+00:00','status':'checked','replay_verified':True,
            'source_sha256':inputs.hashes,'summary':report['summary']}))
        (self.folder/'report.json').write_text(json.dumps(report))
        (self.folder/'report.csv').write_text(report_csv(report))
        (self.folder/'program.py').write_text('# Test source; never executed\n')
        (self.folder/'inputs/payments.csv').write_bytes(self.p)
        (self.folder/'inputs/bank.csv').write_bytes(self.b)

    def files(self,p=None,b=None):return {'payments':('payments.csv',self.p if p is None else p,'text/csv'),'bank':('bank.csv',self.b if b is None else b,'text/csv')}

    def test_root_and_assets_have_security_headers_and_no_keys(self):
        result=self.client.get('/')
        self.assertEqual(result.status_code,200)
        self.assertIn('SettleProof',result.text)
        self.assertNotIn('test-river-key',result.text)
        self.assertEqual(result.headers['x-content-type-options'],'nosniff')
        self.assertIn("frame-ancestors 'none'",result.headers['content-security-policy'])
        self.assertEqual(self.client.get('/static/app.js').status_code,200)
        self.assertEqual(self.client.get('/.env').status_code,404)

    def test_validation_is_real_and_does_not_start_a_job(self):
        result=self.client.post('/api/validate',files=self.files(),headers={'X-SettleProof':'1'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['payments'],7)
        self.assertEqual(result.json()['profiles']['payments'],'standard')
        self.assertFalse(self.service.jobs)

    def test_invalid_currency_and_oversized_input_rejected(self):
        result=self.client.post('/api/validate',files=self.files(p=self.p.replace(b'USD',b'EUR')),headers={'X-SettleProof':'1'})
        self.assertEqual(result.status_code,422)
        self.assertIn('only USD',result.json()['detail'])
        result=self.client.post('/api/validate',files=self.files(p=b'x'*256001),headers={'X-SettleProof':'1'})
        self.assertEqual(result.status_code,413)

    def test_cross_origin_and_unmarked_posts_are_rejected(self):
        self.assertEqual(self.client.post('/api/validate',files=self.files()).status_code,403)
        self.assertEqual(self.client.post('/api/validate',files=self.files(),headers={'X-SettleProof':'1','Origin':'https://foreign.invalid'}).status_code,403)

    def test_oversized_request_rejected_before_job_creation(self):
        result=self.client.post('/api/runs',content=b'x'*600001,headers={'X-SettleProof':'1','Content-Type':'application/octet-stream'})
        self.assertEqual(result.status_code,413)
        self.assertFalse(self.service.jobs)

    def test_run_history_and_report_survive_new_service_instance(self):
        second=RunService(self.settings,self.root)
        second.metadata=StoredMetadata([])
        client=TestClient(create_app(self.settings,root=self.root,service=second))
        result=client.get('/api/runs').json()
        self.assertEqual(result['runs'][0]['run_id'],RID)
        self.assertTrue(result['runs'][0]['report_available'])
        self.assertEqual(client.get('/api/runs/'+RID+'/report').json()['summary']['difference_minor'],-5120)

    def test_remote_only_history_does_not_claim_local_artifacts(self):
        self.service.metadata=StoredMetadata([{'run_id':'sp-20261017T130000-00000000','started_at':'2026-10-17T13:00:00+00:00','status':'checked'}])
        runs=self.client.get('/api/runs').json()['runs']
        remote=next(row for row in runs if row['run_id'].endswith('00000000'))
        self.assertFalse(remote['artifacts_available'])
        self.assertFalse(remote['report_available'])

    def test_downloads_are_attachments_and_cannot_escape_allowlist(self):
        response=self.client.get('/api/runs/'+RID+'/download/payments.csv')
        self.assertEqual(response.content,self.p)
        self.assertIn('attachment',response.headers['content-disposition'])
        self.assertEqual(self.client.get('/api/runs/'+RID+'/download/.env').status_code,404)
        self.assertEqual(self.client.get('/api/runs/not-a-run').status_code,404)

    def test_failed_run_cannot_export_a_stale_report(self):
        path=self.folder/'run.json';manifest=json.loads(path.read_text());manifest['status']='failed';path.write_text(json.dumps(manifest))
        self.assertEqual(self.client.get('/api/runs/'+RID+'/download/report.json').status_code,409)
        self.assertEqual(self.client.get('/api/runs/'+RID+'/report').status_code,409)

    def test_workspace_lock_prevents_second_job(self):
        (self.root/'.local').mkdir();(self.root/'.local/active-run.lock').write_text('external-run')
        result=self.client.post('/api/runs',files=self.files(),headers={'X-SettleProof':'1'})
        self.assertEqual(result.status_code,409)
        self.assertFalse(self.service.jobs)

    def test_attempts_expose_saved_code_and_real_checker_feedback(self):
        folder=self.folder/'attempt-01';folder.mkdir()
        (folder/'program.py').write_text('# rejected test source')
        (folder/'checker.json').write_text(json.dumps({'accepted':False,'feedback':'Fabricated reference'}))
        result=self.client.get('/api/runs/'+RID+'/attempts').json()
        self.assertEqual(result['attempts'][0]['status'],'rejected')
        self.assertEqual(result['attempts'][0]['checker']['feedback'],'Fabricated reference')

