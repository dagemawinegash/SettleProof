# Input formats

Both inputs must be UTF-8 CSVs, at most 256,000 bytes and 200 data records each. Column order can change, but each file must use one complete supported header profile without extra columns. Currency must be USD. Amounts use plain decimal dollars with at most two fractional digits; record identifiers must be unique within each file.

## Standard columns

Payments:

```csv
payment_id,payout_id,kind,amount,fee,currency
ch_1,po_1,charge,120.00,3.60,USD
re_1,po_1,refund,20.00,0.00,USD
```

Bank deposits:

```csv
deposit_id,payout_id,amount,currency
dp_1,po_1,96.40,USD
```

Payment amounts and fees are nonnegative magnitudes. A `refund` subtracts its amount and must have zero fee. Expected net is charges minus refunds and documented fees. Bank amounts are signed net amounts; the app never guesses additional fees.

## Renamed columns

| File | Headers |
| --- | --- |
| Payments | `transaction_reference,settlement_reference,transaction_type,gross_amount,processing_fee,currency_code` |
| Bank | `bank_transaction_id,settlement_reference,net_amount,currency_code` |

Each file can use either profile independently. See [standard samples](../fixtures/demo/) and [renamed samples](../fixtures/alternate/).

## Matching rules

Rows with a shared nonempty payout reference form a group. One bank record can settle that group. Several bank records remain ambiguous even when their sum balances. Blank references remain unassigned; equal amounts alone never establish a match.

Missing deposits and differences may reflect timing or incomplete exports. The app compares the supplied records; it does not verify their authenticity, connect to live payment accounts, or perform financial transactions.
