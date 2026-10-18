import sys, csv, io, hashlib, json
from decimal import Decimal, InvalidOperation

PAYOUT_MAP_P = 'payout_id'
KIND_MAP_P = 'kind'
AMOUNT_MAP_P = 'amount'
FEE_MAP_P = 'fee'
CURRENCY_MAP_P = 'currency'
PAYOUT_MAP_B = 'payout_id'
AMOUNT_MAP_B = 'amount'
CURRENCY_MAP_B = 'currency'


def to_minor(text):
    s = (text or '').strip()
    if s == '':
        return None
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    cents = (d * Decimal(100)).quantize(Decimal(1))
    return int(cents)


def read_records(path):
    with open(path, 'rb') as f:
        raw = f.read()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text, newline=''))
    rows = []
    for row in reader:
        rows.append(row)
    return digest, rows


def main():
    pay_path = sys.argv[1]
    bank_path = sys.argv[2]
    pay_sha, pay_rows = read_records(pay_path)
    bank_sha, bank_rows = read_records(bank_path)

    groups = {}
    order = {}
    unassigned_payment = []
    unassigned_bank = []

    def get_group(pid):
        if pid not in groups:
            groups[pid] = {'payments': [], 'bank': []}
        return groups[pid]

    for i, row in enumerate(pay_rows, start=1):
        pid = (row.get(PAYOUT_MAP_P) or '').strip()
        kind = (row.get(KIND_MAP_P) or '').strip().lower()
        amount_minor = to_minor(row.get(AMOUNT_MAP_P))
        fee_minor = to_minor(row.get(FEE_MAP_P))
        cur = (row.get(CURRENCY_MAP_P) or '').strip().upper()
        if cur and cur != 'USD':
            continue
        if amount_minor is None:
            amount_minor = 0
        if fee_minor is None:
            fee_minor = 0
        if kind == 'refund':
            signed = -abs(amount_minor)
        else:
            signed = abs(amount_minor)
        rid = 'P' + format(i, '06d')
        if pid == '':
            unassigned_payment.append(rid)
        else:
            get_group(pid)['payments'].append((i, rid, signed, fee_minor))

    for i, row in enumerate(bank_rows, start=1):
        pid = (row.get(PAYOUT_MAP_B) or '').strip()
        amount_minor = to_minor(row.get(AMOUNT_MAP_B))
        cur = (row.get(CURRENCY_MAP_B) or '').strip().upper()
        if cur and cur != 'USD':
            continue
        if amount_minor is None:
            amount_minor = 0
        signed = int(amount_minor)
        rid = 'B' + format(i, '06d')
        if pid == '':
            unassigned_bank.append(rid)
        else:
            get_group(pid)['bank'].append((i, rid, signed))

    result_groups = []
    for pid in sorted(groups.keys()):
        g = groups[pid]
        payments_sorted = sorted(g['payments'], key=lambda t: t[0])
        bank_sorted = sorted(g['bank'], key=lambda t: t[0])
        pay_ids = [t[1] for t in payments_sorted]
        bank_ids = [t[1] for t in bank_sorted]
        gross_minor = sum(t[2] for t in payments_sorted)
        fee_minor = sum(t[3] for t in payments_sorted)
        expected_minor = gross_minor - fee_minor
        bank_minor = sum(t[2] for t in bank_sorted)
        difference_minor = bank_minor - expected_minor
        if len(bank_sorted) == 0:
            status = 'missing_deposit'
        elif len(payments_sorted) == 0:
            status = 'unmatched_deposit'
        elif len(bank_sorted) > 1:
            status = 'ambiguous'
        elif len(bank_sorted) == 1 and bank_minor == expected_minor:
            status = 'matched'
        else:
            status = 'discrepancy'
        result_groups.append({
            'payout_id': pid,
            'payment_rows': pay_ids,
            'bank_rows': bank_ids,
            'gross_minor': gross_minor,
            'fee_minor': fee_minor,
            'expected_minor': expected_minor,
            'bank_minor': bank_minor,
            'difference_minor': difference_minor,
            'status': status,
        })

    out = {
        'version': 1,
        'currency': 'USD',
        'source_sha256': {'payments': pay_sha, 'bank': bank_sha},
        'groups': result_groups,
        'unassigned_payment_rows': unassigned_payment,
        'unassigned_bank_rows': unassigned_bank,
    }
    print(json.dumps(out))


if __name__ == '__main__':
    main()
