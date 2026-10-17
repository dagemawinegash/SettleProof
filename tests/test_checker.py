import copy
import json
from pathlib import Path
import unittest

from settleproof.checker import CheckError, canonical, check, report_csv
from settleproof.inputs import Inputs, InputError, minor


ROOT=Path(__file__).resolve().parents[1]
PHEADER='payment_id,payout_id,kind,amount,fee,currency\n'
BHEADER='deposit_id,payout_id,amount,currency\n'


def group(ref,ps,bs,gross,fee,expected,actual,status):
    return {'payout_id':ref,'payment_rows':ps,'bank_rows':bs,'gross_minor':gross,
            'fee_minor':fee,'expected_minor':expected,'bank_minor':actual,
            'difference_minor':actual-expected,'status':status}


def proposal(inputs, groups, up=None, ub=None):
    return {'version':1,'currency':'USD','source_sha256':inputs.hashes,'groups':groups,
            'unassigned_payment_rows':up or [],'unassigned_bank_rows':ub or []}


def demo_candidate(inputs):
    return proposal(inputs,[
        group('po_clear',['P000001','P000002','P000003'],['B000001'],18000,600,17400,17400,'matched'),
        group('po_short',['P000004'],['B000002'],15000,450,14550,14050,'discrepancy'),
        group('po_pending',['P000005'],[],6000,180,5820,0,'missing_deposit'),
        group('po_split',['P000006'],['B000003','B000004'],10000,300,9700,9700,'ambiguous'),
        group('po_unknown',[],['B000006'],0,0,0,1200,'unmatched_deposit')],['P000007'],['B000005'])


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.inputs=Inputs.load(ROOT/'fixtures/demo/payments.csv',ROOT/'fixtures/demo/bank.csv')
        self.candidate=demo_candidate(self.inputs)

    def reject(self, mutate):
        value=copy.deepcopy(self.candidate)
        mutate(value)
        with self.assertRaises(CheckError):
            check(value,self.inputs)

    def test_demo_has_documented_refund_fee_and_true_unresolved_items(self):
        report=check(self.candidate,self.inputs)
        self.assertEqual(report['summary']['expected_minor'],51470)
        self.assertEqual(report['summary']['bank_minor'],46350)
        self.assertEqual(report['summary']['difference_minor'],-5120)
        self.assertEqual(report['summary']['unresolved_items'],6)
        clear=next(g for g in report['groups'] if g['payout_id']=='po_clear')
        refund=clear['evidence']['payments'][2]
        self.assertEqual(refund['gross_minor'],-2000)
        self.assertEqual(refund['source']['payment_id'],'re_001')

    def test_exact_cent_precision_and_exact_match(self):
        inputs=Inputs.from_bytes((PHEADER+'a,p,charge,0.10,0.00,USD\nb,p,charge,0.20,0.00,USD\n').encode(),
                                (BHEADER+'d,p,0.30,USD\n').encode())
        report=check(proposal(inputs,[group('p',['P000001','P000002'],['B000001'],30,0,30,30,'matched')]),inputs)
        self.assertEqual(report['summary']['difference_minor'],0)

    def test_fabricated_row_rejected(self):
        self.reject(lambda x:x['groups'][0]['payment_rows'].append('P999999'))

    def test_reused_row_rejected(self):
        self.reject(lambda x:x['groups'][1]['payment_rows'].append('P000001'))

    def test_reused_bank_record_within_group_rejected(self):
        self.reject(lambda x:x['groups'][0]['bank_rows'].append('B000001'))

    def test_omitted_payment_rejected_even_if_totals_are_edited(self):
        def omit(value):
            g=value['groups'][0]
            g['payment_rows'].pop()
            g['gross_minor']=20000; g['expected_minor']=19400
            g['difference_minor']=-2000; g['status']='discrepancy'
        self.reject(omit)

    def test_missing_whole_group_rejected(self):
        self.reject(lambda x:x['groups'].pop())

    def test_invented_fee_to_hide_shortfall_rejected(self):
        def hide(value):
            g=value['groups'][1]
            g.update(fee_minor=950,expected_minor=14050,difference_minor=0,status='matched')
        self.reject(hide)

    def test_wrong_total_rejected(self):
        self.reject(lambda x:x['groups'][0].update(bank_minor=999999))

    def test_float_and_boolean_money_rejected(self):
        for value in (17400.0,True):
            with self.subTest(value=value):
                self.reject(lambda x:x['groups'][0].update(bank_minor=value))

    def test_bank_reference_mismatch_rejected_even_if_amounts_match(self):
        self.reject(lambda x:x['groups'][0].update(bank_rows=['B000005']))

    def test_multiple_bank_deposits_cannot_be_called_a_match(self):
        self.reject(lambda x:x['groups'][3].update(status='matched'))

    def test_equal_amounts_with_blank_references_remain_unassigned(self):
        report=check(self.candidate,self.inputs)
        self.assertEqual(report['unassigned_payment_rows'][0]['net_minor'],4000)
        self.assertEqual(report['unassigned_bank_rows'][0]['net_minor'],4000)
        self.reject(lambda x:x['unassigned_payment_rows'].clear())

    def test_tampered_source_hash_rejected(self):
        self.reject(lambda x:x['source_sha256'].update(payments='0'*64))

    def test_unknown_extra_fields_cannot_smuggle_adjustments(self):
        self.reject(lambda x:x['groups'][0].update(adjustment_minor=500))

    def test_replay_normalization_ignores_array_order_only(self):
        value=copy.deepcopy(self.candidate)
        value['groups'].reverse()
        value['groups'][-1]['payment_rows'].reverse()
        self.assertEqual(canonical(self.candidate),canonical(value))
        value['groups'][0]['bank_minor']+=1
        self.assertNotEqual(canonical(self.candidate),canonical(value))

    def test_report_csv_contains_unreferenced_rows_and_formula_guard(self):
        text=report_csv(check(self.candidate,self.inputs))
        self.assertIn('unreferenced,P000007',text)
        report=check(self.candidate,self.inputs)
        report['groups'][0]['payout_id']='=HYPERLINK("bad")'
        self.assertIn("'=HYPERLINK",report_csv(report))


class InputTests(unittest.TestCase):
    def load_payment(self, line, bank=None):
        return Inputs.from_bytes((PHEADER+line).encode(),(BHEADER+(bank or 'd,p,1.00,USD\n')).encode())

    def test_mixed_currency_rejected_before_agent_calls(self):
        with self.assertRaises(InputError):
            self.load_payment('a,p,charge,1.00,0.00,EUR\n')

    def test_invalid_money_formats_rejected(self):
        for value in ('NaN','Infinity','1e2','1.001','1,000.00','+1','-1.00','0x10','01.00'):
            with self.subTest(value=value),self.assertRaises(InputError):
                minor(value)

    def test_duplicate_identifiers_rejected(self):
        with self.assertRaises(InputError):
            self.load_payment('a,p,charge,1.00,0.00,USD\na,q,charge,1.00,0.00,USD\n')

    def test_refund_fee_unsupported(self):
        with self.assertRaises(InputError):
            self.load_payment('a,p,refund,1.00,0.10,USD\n')

    def test_negative_net_and_negative_bank_allowed(self):
        value=self.load_payment('a,p,refund,1.00,0.00,USD\n', 'd,p,-1.00,USD\n')
        report=check(proposal(value,[group('p',['P000001'],['B000001'],-100,0,-100,-100,'matched')]),value)
        self.assertEqual(report['summary']['difference_minor'],0)

    def test_bom_reordered_headers_crlf_and_multiline_ids_have_stable_record_ids(self):
        p=b'\xef\xbb\xbfcurrency,fee,amount,kind,payout_id,payment_id\r\nUSD,0,1.00,charge,p,"a\nb"\r\n'
        inputs=Inputs.from_bytes(p,(BHEADER+'d,p,1.00,USD\n').encode())
        self.assertEqual(inputs.payments[0].row_id,'P000001')
        self.assertEqual(inputs.payments[0].source['payment_id'],'a\nb')
        self.assertEqual(len(inputs.hashes['payments']),64)

    def test_size_and_record_limits(self):
        with self.assertRaises(InputError):
            Inputs.from_bytes(b'x'*256001,b'')
        rows=''.join(f'a{i},p,charge,1,0,USD\n' for i in range(201))
        with self.assertRaises(InputError):
            self.load_payment(rows)

    def test_duplicate_or_extra_headers_and_missing_cells_rejected(self):
        for p in (b'payment_id,payout_id,kind,amount,fee,currency,currency\na,p,charge,1,0,USD,USD\n',
                  b'payment_id,payout_id,kind,amount,fee,currency\na,p,charge,1,USD\n'):
            with self.subTest(p=p),self.assertRaises(InputError):
                Inputs.from_bytes(p,(BHEADER+'d,p,1,USD\n').encode())


if __name__=='__main__':
    unittest.main()
