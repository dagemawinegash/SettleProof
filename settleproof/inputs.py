"""Trusted, deliberately narrow CSV contracts and exact USD arithmetic."""
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import io
from pathlib import Path
import re

MAX_BYTES = 256_000
MAX_ROWS = 200
PAYMENT_COLUMNS = {'payment_id','payout_id','kind','amount','fee','currency'}
BANK_COLUMNS = {'deposit_id','payout_id','amount','currency'}
MONEY = re.compile(r'-?(?:0|[1-9]\d{0,10})(?:\.\d{1,2})?\Z')


class InputError(ValueError):
    pass


def minor(value, *, signed=False):
    if not isinstance(value,str) or not MONEY.fullmatch(value):
        raise InputError('Amounts must be plain decimal USD with at most two decimal places')
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise InputError('Invalid amount') from None
    if not signed and number < 0:
        raise InputError('Payment amount and fee must be nonnegative; kind supplies the sign')
    return int(number * 100)


@dataclass(frozen=True)
class Row:
    row_id: str
    record: int
    source: dict
    payout_id: str
    gross_minor: int
    fee_minor: int
    net_minor: int


@dataclass(frozen=True)
class Inputs:
    payments: tuple[Row,...]
    bank: tuple[Row,...]
    payment_bytes: bytes
    bank_bytes: bytes

    @property
    def hashes(self):
        return {'payments':hashlib.sha256(self.payment_bytes).hexdigest(),
                'bank':hashlib.sha256(self.bank_bytes).hexdigest()}

    @classmethod
    def load(cls, payments, bank):
        return cls.from_bytes(Path(payments).read_bytes(), Path(bank).read_bytes())

    @classmethod
    def from_bytes(cls, payment_bytes, bank_bytes):
        return cls(_parse(payment_bytes, True), _parse(bank_bytes, False), payment_bytes, bank_bytes)


def _parse(data, payment):
    label = 'payments' if payment else 'bank'
    if len(data) > MAX_BYTES:
        raise InputError(f'{label}: maximum file size is {MAX_BYTES} bytes')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise InputError(f'{label}: UTF-8 CSV required') from None
    try:
        reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
        columns = PAYMENT_COLUMNS if payment else BANK_COLUMNS
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)) or set(reader.fieldnames)!=columns:
            raise InputError(f'{label}: required columns are {", ".join(sorted(columns))}; no duplicate or extra columns')
        parsed, seen = [], set()
        for i, row in enumerate(reader, 1):
            if i > MAX_ROWS:
                raise InputError(f'{label}: maximum {MAX_ROWS} records')
            if None in row or any(v is None for v in row.values()):
                raise InputError(f'{label}: malformed record {i}')
            if any(len(v)>200 or '\x00' in v for v in row.values()):
                raise InputError(f'{label}: oversized or invalid field at record {i}')
            row = {k:v.strip() for k,v in row.items()}
            identity = row['payment_id' if payment else 'deposit_id']
            if not identity or identity in seen:
                raise InputError(f'{label}: empty or duplicate record identifier at record {i}')
            seen.add(identity)
            if row['currency']!='USD':
                raise InputError(f'{label}: only USD is supported; mixed currencies cannot be compared')
            amount = minor(row['amount'], signed=not payment)
            fee = minor(row['fee']) if payment else 0
            if payment:
                if row['kind'] not in ('charge','refund'):
                    raise InputError(f'{label}: kind must be charge or refund')
                if row['kind']=='refund' and fee!=0:
                    raise InputError(f'{label}: refund fees are unsupported; fee must be 0')
                amount *= 1 if row['kind']=='charge' else -1
            parsed.append(Row(('P' if payment else 'B')+f'{i:06}', i, row,
                              row['payout_id'], amount, fee, amount-fee))
        if not parsed:
            raise InputError(f'{label}: at least one data record is required')
        return tuple(parsed)
    except csv.Error:
        raise InputError(f'{label}: invalid CSV syntax') from None
