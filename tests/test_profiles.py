from pathlib import Path
import unittest

from settleproof.checker import check
from settleproof.inputs import Inputs, InputError
from test_checker import demo_candidate

ROOT=Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def test_alternate_profile_keeps_original_column_evidence_and_money(self):
        value=Inputs.load(ROOT/'fixtures/alternate/payments.csv',ROOT/'fixtures/alternate/bank.csv')
        self.assertEqual(value.profiles,{'payments':'renamed','bank':'renamed'})
        report=check(demo_candidate(value),value)
        self.assertEqual(report['summary']['difference_minor'],-5120)
        self.assertEqual(report['groups'][0]['evidence']['payments'][0]['source']['transaction_reference'],'ch_001')
        self.assertEqual(value.column_maps['bank']['amount'],'net_amount')

    def test_profiles_can_differ_between_sources(self):
        value=Inputs.load(ROOT/'fixtures/demo/payments.csv',ROOT/'fixtures/alternate/bank.csv')
        self.assertEqual(value.profiles,{'payments':'standard','bank':'renamed'})
        self.assertEqual(check(demo_candidate(value),value)['summary']['difference_minor'],-5120)

    def test_ambiguous_mixed_header_schema_is_rejected(self):
        p=(ROOT/'fixtures/demo/payments.csv').read_bytes().replace(b'payment_id,',b'transaction_reference,')
        with self.assertRaises(InputError):
            Inputs.from_bytes(p,(ROOT/'fixtures/demo/bank.csv').read_bytes())
