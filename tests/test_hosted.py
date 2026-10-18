import shutil
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from settleproof.hosted import protect
import test_server as fixtures

RID=fixtures.RID

CODE='test-owner-access-code-at-least-20'
PRIVATE='sp-20261017T130000-abcdef12'


class HostedAccessTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.BrowserApiTests('test_root_and_assets_have_security_headers_and_no_keys')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.app=protect(self.fixture.client.app,CODE,RID,secure=False)
        self.client=TestClient(self.app)
        shutil.copytree(self.fixture.folder,self.fixture.root/'artifacts'/PRIVATE)

    def login(self,code=CODE):
        return self.client.post('/api/session',json={'code':code},headers={'X-SettleProof':'1'})

    def test_public_history_and_artifacts_are_limited_to_seed(self):
        result=self.client.get('/api/runs').json()
        self.assertEqual([row['run_id'] for row in result['runs']],[RID])
        self.assertEqual(self.client.get('/api/runs/'+RID+'/report').status_code,200)
        self.assertEqual(self.client.get('/api/runs/'+PRIVATE+'/report').status_code,401)
        self.assertEqual(self.client.get('/api/runs/'+PRIVATE+'/download/payments.csv').status_code,401)
        self.assertEqual(self.client.post('/api/runs',files=self.fixture.files(),headers={'X-SettleProof':'1'}).status_code,401)
        self.assertFalse(self.fixture.service.jobs)

    def test_owner_cookie_unlocks_private_history_and_start(self):
        result=self.login()
        self.assertEqual(result.status_code,200)
        self.assertIn('HttpOnly',result.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/runs/'+PRIVATE+'/report').status_code,200)
        with patch.object(self.fixture.service,'start',return_value=PRIVATE) as start:
            response=self.client.post('/api/runs',files=self.fixture.files(),headers={'X-SettleProof':'1'})
            self.assertEqual(response.status_code,202)
            start.assert_called_once()

    def test_login_has_origin_boundary_and_attempt_limit(self):
        self.assertEqual(self.client.post('/api/session',json={'code':CODE}).status_code,403)
        self.assertEqual(self.client.post('/api/session',json={'code':CODE},headers={'X-SettleProof':'1','Origin':'https://evil.invalid'}).status_code,403)
        for _ in range(5):
            self.assertEqual(self.login('incorrect').status_code,401)
        self.assertEqual(self.login().status_code,429)

    def test_hosted_health_does_not_expose_owner_code(self):
        response=self.client.get('/api/health')
        self.assertTrue(response.json()['hosted'])
        self.assertFalse(response.json()['owner'])
        self.assertNotIn(CODE,response.text)
        self.login()
        self.assertTrue(self.client.get('/api/health').json()['owner'])
