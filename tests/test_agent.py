from contextlib import nullcontext
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from settleproof.agent import Agent, active_run
from settleproof.config import Settings
from settleproof.inputs import Inputs, InputError
from settleproof.replay import replay_saved
from test_checker import ROOT, demo_candidate


class FakeRiver:
    """Controlled integration double; never represented as live model execution."""
    def __init__(self):
        self.calls=[]

    def models(self):
        return [Settings.model]

    def generate(self, context, previous=None, feedback=None):
        self.calls.append((previous,feedback))
        return 'print("test double; not run locally")',{'usage':{'total_tokens':1}}


class FakeSandbox:
    def __init__(self, results):
        self.results=iter(results)
        self.deleted=[]
        self.executions=0

    def create(self,name):
        return 'test-owned-sandbox'

    def ready(self,sandbox_id):
        return {'status':'running'}

    def prepare(self,sandbox_id,inputs):
        return {'test_double':True}

    def run(self,*args):
        self.executions+=1
        return copy.deepcopy(next(self.results))

    def delete(self,sandbox_id):
        self.deleted.append(sandbox_id)


class FakeMetadata:
    def __init__(self):
        self.rows={}

    def save(self,manifest):
        self.rows[manifest['run_id']]=copy.deepcopy(manifest)

    def verify(self,run_id):
        return self.rows.get(run_id)


class AgentTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.local').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'.local',prefix='test-')
        self.addCleanup(self.tmp.cleanup)
        self.output=Path(self.tmp.name)
        self.p=ROOT/'fixtures/demo/payments.csv'
        self.b=ROOT/'fixtures/demo/bank.csv'
        self.inputs=Inputs.load(self.p,self.b)
        self.candidate=demo_candidate(self.inputs)
        self.good={'exit_code':0,'stdout':json.dumps(self.candidate),'stderr':'',
                   'timed_out':False,'output_truncated':False}
        self.bad={'exit_code':1,'stdout':'','stderr':'NameError: name cents is not defined',
                  'timed_out':False,'output_truncated':False}
        self.river=FakeRiver()
        self.metadata=FakeMetadata()
        self.lock=patch('settleproof.agent.active_run',return_value=nullcontext())
        self.lock.start()
        self.addCleanup(self.lock.stop)

    def agent(self,results):
        self.sandbox=FakeSandbox(results)
        return Agent(Settings('test-key','test-key'),river=self.river,sandbox=self.sandbox,
                     metadata=self.metadata,emit=lambda _:None)

    def test_execution_failure_is_repaired_using_actual_feedback(self):
        agent=self.agent([self.bad,self.good,self.good])
        folder,manifest=agent.run(self.p,self.b,output=self.output)
        self.assertEqual(manifest['status'],'checked')
        self.assertEqual(len(self.river.calls),2)
        self.assertIn('NameError',self.river.calls[1][1])
        self.assertTrue(manifest['replay_verified'])
        self.assertTrue(manifest['metadata_readback_verified'])
        self.assertEqual(self.sandbox.deleted,['test-owned-sandbox'])
        self.assertTrue((folder/'report.csv').exists())

    def test_checker_rejection_is_fed_back_without_publishing_report(self):
        tampered=copy.deepcopy(self.candidate)
        tampered['groups'][1]['fee_minor']=999
        invalid={**self.good,'stdout':json.dumps(tampered)}
        folder,manifest=self.agent([invalid,self.good,self.good]).run(self.p,self.b,output=self.output)
        self.assertEqual([x['status'] for x in manifest['attempts']],['rejected','accepted'])
        self.assertIn('Incorrect fee_minor',self.river.calls[1][1])

    def test_three_failures_stop_and_delete_worker(self):
        with self.assertRaisesRegex(RuntimeError,'attempt budget'):
            self.agent([self.bad]*3).run(self.p,self.b,output=self.output)
        self.assertEqual(len(self.river.calls),3)
        folder=next(self.output.iterdir())
        self.assertFalse((folder/'report.json').exists())
        self.assertEqual(json.loads((folder/'run.json').read_text())['status'],'failed')
        self.assertEqual(self.sandbox.deleted,['test-owned-sandbox'])

    def test_replay_crash_cannot_be_treated_as_success(self):
        with self.assertRaises(RuntimeError):
            self.agent([self.good,self.bad]).run(self.p,self.b,output=self.output,max_attempts=1)
        folder=next(self.output.iterdir())
        self.assertFalse((folder/'report.json').exists())
        manifest=json.loads((folder/'run.json').read_text())
        self.assertFalse(manifest['replay_verified'])
        self.assertEqual(manifest['status'],'failed')
        self.assertEqual(self.sandbox.deleted,['test-owned-sandbox'])

    def test_saved_program_replays_remotely_without_model_call(self):
        agent=self.agent([self.good,self.good,self.good])
        folder,manifest=agent.run(self.p,self.b,output=self.output)
        with patch('settleproof.replay.active_run',return_value=nullcontext()):
            path,result=replay_saved(Settings('test-key','test-key'),folder,sandbox=self.sandbox)
        self.assertEqual(result['status'],'checked')
        self.assertFalse(result['model_called'])
        self.assertEqual(len(self.river.calls),1)
        self.assertEqual(len(self.sandbox.deleted),2)
        self.assertTrue(path.exists())

    def test_changed_saved_program_is_rejected_before_remote_execution(self):
        agent=self.agent([self.good,self.good])
        folder,manifest=agent.run(self.p,self.b,output=self.output)
        (folder/'program.py').write_text('print("tampered")')
        with self.assertRaisesRegex(ValueError,'has changed'):
            replay_saved(Settings('test-key','test-key'),folder,sandbox=self.sandbox)
        self.assertEqual(self.sandbox.executions,2)

    def test_truncated_success_output_is_rejected(self):
        result={**self.good,'output_truncated':True}
        with self.assertRaises(RuntimeError):
            self.agent([result]).run(self.p,self.b,output=self.output,max_attempts=1)

    def test_malformed_output_is_rejected(self):
        result={**self.good,'stdout':'Traceback then not JSON'}
        with self.assertRaises(RuntimeError):
            self.agent([result]).run(self.p,self.b,output=self.output,max_attempts=1)

    def test_unsupported_input_stops_before_inference(self):
        invalid=self.output/'invalid.csv'
        invalid.write_text('bad,headers\n1,2\n')
        agent=self.agent([])
        with self.assertRaises(InputError):
            agent.run(invalid,self.b,output=self.output/'runs')
        self.assertEqual(self.river.calls,[])
        self.assertEqual(self.sandbox.executions,0)

    def test_concurrent_run_lock_and_release(self):
        root=self.output/'locks'
        with active_run(root):
            with self.assertRaisesRegex(RuntimeError,'Another run'):
                with active_run(root):
                    self.fail('second job entered lock')
        with active_run(root):
            self.assertTrue((root/'active-run.lock').exists())
        self.assertFalse((root/'active-run.lock').exists())


if __name__=='__main__':
    unittest.main()
