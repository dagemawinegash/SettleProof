"""Trusted verifier: never import or execute candidate Python on the controller."""
from collections import Counter
import csv
from dataclasses import asdict
import io
import json

from .inputs import Inputs


class CheckError(ValueError):
    pass


GROUP_KEYS = {'payout_id','payment_rows','bank_rows','gross_minor','fee_minor',
              'expected_minor','bank_minor','difference_minor','status'}
TOTAL_KEYS = ('gross_minor','fee_minor','expected_minor','bank_minor','difference_minor')


def check(candidate, inputs: Inputs):
    """Validate an untrusted proposal, then produce an evidence-bearing report.

    Every payout is indivisible in this profile; it has zero or one bank deposit.
    Multiple deposits with the same reference remain ambiguous, even if they sum
    to the payout. Unreferenced rows may never be attributed by amount alone.
    """
    def require(condition, message):
        if not condition:
            raise CheckError(message)

    require(isinstance(candidate,dict), 'Result must be an object')
    require(set(candidate)=={'version','currency','source_sha256','groups',
                            'unassigned_payment_rows','unassigned_bank_rows'}, 'Invalid top-level result fields')
    require(type(candidate['version']) is int and candidate['version']==1, 'Unsupported result version')
    require(candidate['currency']=='USD', 'Currency must be USD')
    require(candidate['source_sha256']==inputs.hashes, 'Source hashes do not match immutable inputs')
    require(isinstance(candidate['groups'],list), 'groups must be an array')
    require(len(candidate['groups'])<=400, 'Too many proposed groups')
    all_p={r.row_id:r for r in inputs.payments}
    all_b={r.row_id:r for r in inputs.bank}
    used_p, used_b, used_refs = [], [], []
    checked_groups = []
    for group in candidate['groups']:
        require(isinstance(group,dict) and set(group)==GROUP_KEYS, 'Invalid group fields')
        ref=group['payout_id']
        require(isinstance(ref,str) and bool(ref), 'Each group needs a nonempty payout reference')
        require(ref not in used_refs, 'Payout reference repeated across groups')
        used_refs.append(ref)
        for key, source, used in [('payment_rows',all_p,used_p),('bank_rows',all_b,used_b)]:
            ids=group[key]
            require(isinstance(ids,list) and all(isinstance(i,str) for i in ids), f'{key} must be row ID arrays')
            require(len(ids)==len(set(ids)), 'A row is reused within a group')
            require(all(i in source for i in ids),
                    f'Fabricated source row reference in {key}: use record-based P000001/B000001 IDs, never CSV payment_id/deposit_id values')
            require(not set(ids).intersection(used), 'A row is reused across groups')
            expected={i for i,r in source.items() if r.payout_id==ref}
            require(set(ids)==expected, 'Group must include every source row with its payout reference')
            used.extend(ids)
        ps=[all_p[i] for i in group['payment_rows']]
        bs=[all_b[i] for i in group['bank_rows']]
        require(bool(ps or bs), 'Empty invented payout group')
        gross=sum(r.gross_minor for r in ps)
        fee=sum(r.fee_minor for r in ps)
        expected=gross-fee
        actual=sum(r.net_minor for r in bs)
        computed=(gross,fee,expected,actual,actual-expected)
        for key,total in zip(TOTAL_KEYS,computed):
            hint='; difference is bank_minor - expected_minor for EVERY status, including missing deposits' if key=='difference_minor' else ''
            require(type(group[key]) is int and group[key]==total, f'Incorrect {key}; recompute from source rows'+hint)
        status = ('unmatched_deposit' if not ps else 'missing_deposit' if not bs else
                  'ambiguous' if len(bs)>1 else 'matched' if actual==expected else 'discrepancy')
        require(group['status']==status, 'Status is inconsistent with source evidence')
        copied={**group,'payment_rows':sorted(group['payment_rows']), 'bank_rows':sorted(group['bank_rows'])}
        copied['evidence']={'payments':[asdict(r) for r in sorted(ps,key=lambda r:r.row_id)],
                            'bank':[asdict(r) for r in sorted(bs,key=lambda r:r.row_id)]}
        checked_groups.append(copied)
    unassigned={}
    for key,source,used in [('unassigned_payment_rows',all_p,used_p),('unassigned_bank_rows',all_b,used_b)]:
        ids=candidate[key]
        require(isinstance(ids,list) and all(isinstance(i,str) for i in ids), f'{key} must be a row ID array')
        require(len(ids)==len(set(ids)), 'An unassigned row is reused')
        require(set(ids)=={i for i,r in source.items() if not r.payout_id}, 'Only rows without payout references belong in unassigned rows')
        require(not set(ids).intersection(used), 'An assigned row is repeated as unassigned')
        require(set(used).union(ids)==set(source), 'Source coverage is incomplete')
        unassigned[key]=[asdict(source[i]) for i in sorted(ids)]
    counts=dict(Counter(g['status'] for g in checked_groups))
    payments_net=sum(r.net_minor for r in inputs.payments)
    bank_net=sum(r.net_minor for r in inputs.bank)
    unresolved=sum(g['status']!='matched' for g in checked_groups)+sum(len(v) for v in unassigned.values())
    return {'version':1,'checked':True,'currency':'USD','source_sha256':inputs.hashes,
            'summary':{'payment_records':len(all_p),'bank_records':len(all_b),'group_counts':counts,
                       'unresolved_items':unresolved,'gross_minor':sum(r.gross_minor for r in inputs.payments),
                       'fee_minor':sum(r.fee_minor for r in inputs.payments),
                       'expected_minor':payments_net,'bank_minor':bank_net,'difference_minor':bank_net-payments_net},
            'groups':sorted(checked_groups,key=lambda g:g['payout_id']),**unassigned,
            'interpretation':'Differences need investigation. Timing, missing exports, and unsupported split deposits can explain unresolved items. A difference alone does not establish lost funds or fraud.'}


def canonical(candidate):
    """Order-independent representation for exact replay comparison."""
    clone=json.loads(json.dumps(candidate))
    for group in clone['groups']:
        group['payment_rows']=sorted(group['payment_rows'])
        group['bank_rows']=sorted(group['bank_rows'])
    clone['groups']=sorted(clone['groups'],key=lambda g:g['payout_id'])
    for key in ('unassigned_payment_rows','unassigned_bank_rows'):
        clone[key]=sorted(clone[key])
    return json.dumps(clone,sort_keys=True,separators=(',',':'))


def report_csv(report):
    buffer=io.StringIO(newline='')
    writer=csv.writer(buffer,lineterminator='\n')
    writer.writerow(['payout_id','status','payment_rows','bank_rows',*TOTAL_KEYS,'currency'])
    def safe(value):
        # Guard spreadsheet formula execution in untrusted text identifiers.
        return "'"+value if isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r')) else value
    for g in report['groups']:
        writer.writerow([safe(g['payout_id']),g['status'],' '.join(g['payment_rows']),
                         ' '.join(g['bank_rows']),*[g[k] for k in TOTAL_KEYS],'USD'])
    for key in ('unassigned_payment_rows','unassigned_bank_rows'):
        for row in report[key]:
            payment=key=='unassigned_payment_rows'
            writer.writerow(['','unreferenced',row['row_id'] if payment else '',
                             '' if payment else row['row_id'],row['gross_minor'] if payment else 0,
                             row['fee_minor'],row['net_minor'] if payment else 0,
                             0 if payment else row['net_minor'],
                             -row['net_minor'] if payment else row['net_minor'],'USD'])
    return buffer.getvalue()
