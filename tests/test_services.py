import io
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from settleproof.config import Settings
from settleproof.createos import CreateOS
from settleproof.http import Http, ServiceError


class ServiceTests(TestCase):
    def test_service_error_redacts_key_echo_and_omits_request_inputs(self):
        secret='private-test-credential'
        body=json.dumps({'status':'fail','data':{'error':'Rejected '+secret},
                         'request_inputs':'do not expose this'}).encode()
        error=HTTPError('https://test.invalid',400,'bad request',{},io.BytesIO(body))
        with patch('urllib.request.urlopen',side_effect=error):
            with self.assertRaises(ServiceError) as caught:
                Http('https://test.invalid',{'Authorization':'Bearer '+secret}).request('POST','/test',{})
        self.assertNotIn(secret,str(caught.exception))
        self.assertNotIn('do not expose this',str(caught.exception))
        self.assertIn('[REDACTED]',str(caught.exception))

    def test_rate_limit_retry_budget_is_bounded(self):
        errors=[HTTPError('https://test.invalid',429,'rate limit',{},io.BytesIO(b'{}')) for _ in range(3)]
        with patch('urllib.request.urlopen',side_effect=errors) as request, patch('settleproof.http.time.sleep') as sleep:
            with self.assertRaises(ServiceError):
                Http('https://test.invalid',{}).request('POST','/test',{},retries=2)
        self.assertEqual(request.call_count,3)
        self.assertEqual(sleep.call_count,2)

    def test_creation_is_not_retried_on_uncertain_network_failure(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError()) as request:
            with self.assertRaises(ServiceError):
                Http('https://test.invalid',{}).request('POST','/v1/sandboxes',{})
        self.assertEqual(request.call_count,1)

    def test_delete_waits_for_terminal_state(self):
        client=CreateOS(Settings('test-key','test-key'))
        client.call=MagicMock(side_effect=[{'status':'destroying'},{'status':'destroyed'}])
        client.delete('owned-test-id')
        self.assertEqual(client.call.call_count,2)
        self.assertEqual(client.call.call_args.args[:2],('GET','/v1/sandboxes/owned-test-id'))

    def test_delete_accepts_not_found_after_delete_was_accepted(self):
        client=CreateOS(Settings('test-key','test-key'))
        client.call=MagicMock(side_effect=[{'status':'destroying'},ServiceError('not found',status=404)])
        client.delete('owned-test-id')
        self.assertEqual(client.call.call_count,2)
