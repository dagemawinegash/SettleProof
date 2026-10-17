# SettleProof

An agent that writes and runs Python to compare payment-provider CSV exports with bank deposits. An independent checker verifies every source reference, amount, and matching claim before accepting its report.

Built for the CreateOS × Stripe Projects hackathon, October 17, 2026. **Phases 1–3 are implemented: a real coding agent, independent reconciliation checks, and a local browser workspace.** Deployment and submission are Phase 4.

## Browser workspace

From the repository root in WSL:

```sh
.venv/bin/python -m pip install -e '.[web]'
.venv/bin/python -m settleproof serve
```

Open **http://127.0.0.1:8000**. In the existing development workspace the web dependencies are already installed. PowerShell users can run `.\.venv-win\Scripts\python.exe -m settleproof serve` instead. Add `--port 8001` if port 8000 is occupied.

Choose **New reconciliation**, select your two supported CSVs, or **Load samples** for synthetic data. Standard and renamed-column samples are available. Loading samples only validates the files; **Reconcile files** starts real River inference and CreateOS execution.

The workspace provides:

- Actual controller progress, revision feedback, and cancellation at a safe checkpoint.
- Checked totals and a searchable ledger with needs-review/matched filters.
- A payout detail panel with exact fee/refund arithmetic and expandable original CSV fields.
- **Execution evidence** showing actual generated programs, checker decisions, execution status, and token usage.
- **Export report** downloads for CSV/JSON reports, accepted Python, and the original input files.
- **Run history** backed by Neon metadata, with local artifact availability shown. Completed runs survive a server restart.

The latest locally available checked run opens automatically. Synthetic samples are explicitly labeled. On smaller screens the evidence panel sits below the ledger; selecting a record scrolls to its evidence. The ledger scrolls horizontally when needed. Keyboard shortcuts: `N` opens file import, `/` focuses search, and arrow keys navigate focused ledger rows.

The browser app binds to loopback and is intended for a single local user. Public deployment and access controls remain Phase 4. [Interface references and design decisions](docs/interface-design.md) document the Modern Treasury, Linear, and TailAdmin research; the implemented markup, styles, and illustration are original.

## How it works

1. The trusted controller validates two CSVs and preserves their original bytes.
2. River GLM writes a complete Python program for the declared file contract.
3. CreateOS executes that program in a disposable EU sandbox without controller credentials.
4. The independent controller checks the result. Execution/check failures feed back to the model, with a maximum of three generated programs.
5. A successful program runs again on the same files. Both results must pass checks and agree before the report and program are exported.

The first live integration run needed a real revision: its generated program omitted unreferenced rows, the checker rejected it, and the revised program passed. Attempt artifacts record actual results; revisions are never staged for a demo.

## Run locally

Requires Python 3.11+, a River inference key, CreateOS EU Sandbox access, and Postgres. Stripe Projects manages service credentials. Generated Python runs in CreateOS; the controller runs locally.

In an authenticated, initialized Stripe project, provision the free metadata database and manage the two existing API keys:

```sh
stripe projects catalog Neon --json
stripe projects add Neon/free --name metadata-plan --accept-tos --yes
stripe projects add Neon/postgres --name run-metadata --accept-tos --yes
stripe projects variables set river-api-key --env-key RIVER_API_KEY
stripe projects variables set createos-api-key --env-key CREATEOS_API_KEY
stripe projects env --pull
```

The variables commands prompt for the keys. Skip provisioning services that already exist. Do not hand-edit `.projects/` or the managed `.env`.

For WSL/Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m settleproof doctor
.venv/bin/python -u -m settleproof run fixtures/demo/payments.csv fixtures/demo/bank.csv
```

The existing development workspace already has a prepared `.venv`. On another Linux machine, virtual-environment creation requires the distribution's Python venv/ensurepip package.

For Windows PowerShell:

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -e .
.\.venv-win\Scripts\python.exe -m settleproof doctor
.\.venv-win\Scripts\python.exe -u -m settleproof run fixtures/demo/payments.csv fixtures/demo/bank.csv
```

Configuration names (values stay private): `RIVER_API_KEY`, `CREATEOS_API_KEY`, and `RUN_METADATA_CONNECTION_STRING` (or `DATABASE_URL`). Optional `RIVER_MODEL` defaults to `zai-org/GLM-5.3-Flash`; `doctor` verifies that the key can access it. CreateOS uses `https://api-eu.sb.createos.sh`; River uses `https://api.river.ai/v1`.

## Supported input contract

Files are UTF-8 CSV, at most 256,000 bytes and 200 data records each. Column order may change; column names must match one of the two explicit profiles, with no extras. Currency must be USD throughout. Amounts use plain decimal dollars with at most two fractional digits. Identifiers must be unique within their respective file.

Payments:

```csv
payment_id,payout_id,kind,amount,fee,currency
ch_1,po_1,charge,120.00,3.60,USD
re_1,po_1,refund,20.00,0.00,USD
```

Bank:

```csv
deposit_id,payout_id,amount,currency
dp_1,po_1,96.40,USD
```

Payment amounts and fees are nonnegative magnitudes; `refund` supplies a negative sign. Refund fee must be zero. Expected net is signed payment amounts minus documented fees. Bank amounts are signed net amounts. No fees are guessed or subtracted from bank amounts.

All rows sharing a nonempty `payout_id` belong to one group. One bank record can settle that group. Multiple bank records remain ambiguous, including when their sum balances. Blank references remain unassigned; equal amounts alone never establish a match. Missing deposits and unexplained differences need investigation and may reflect settlement timing or incomplete exports.

The **renamed** profile uses the same financial rules with these actual headers:

| Source | Renamed CSV headers |
| --- | --- |
| Payments | `transaction_reference,settlement_reference,transaction_type,gross_amount,processing_fee,currency_code` |
| Bank | `bank_transaction_id,settlement_reference,net_amount,currency_code` |

Each file can use either complete profile independently. The model receives the declared column mapping and generates code that reads the actual headers. Original header names remain in the evidence. See [alternate payment sample](fixtures/alternate/payments.csv) and [alternate bank sample](fixtures/alternate/bank.csv).

These are explicit prototype schemas, not universal adapters for arbitrary bank or Stripe exports. There is no live Stripe payments integration or automatic financial action.

## Reports and replay

Each run saves an ignored local `artifacts/sp-.../` directory:

| Artifact | Purpose |
| --- | --- |
| `report.json` | Independently checked totals and full source-row evidence |
| `report.csv` | Spreadsheet report, including unreferenced rows; amounts are integer USD cents |
| `program.py` | Accepted generated Python, runnable with the two input paths |
| `inputs/` | Original source bytes |
| `attempt-*/` | Generated programs, model token usage, execution output, and check feedback |
| `run.json`, `events.jsonl`, `replay.json` | Run identity, sandbox policy/cleanup, progress, and original replay evidence |

Rerun a saved accepted program **in a new CreateOS sandbox**, with no new inference call:

```sh
.venv/bin/python -m settleproof replay artifacts/REPLACE_WITH_RUN_ID
```

The replay checks saved source hashes and input hashes, validates the new result, compares the full evidence report, and deletes its sandbox. Evidence is written under the original run's `replays/` directory.

Check any candidate result against original files without a model, sandbox, or credentials:

```sh
.venv/bin/python -m settleproof check fixtures/demo/payments.csv fixtures/demo/bank.csv artifacts/RUN_ID/attempt-01/candidate.json
```

The synthetic demo intentionally contains a matched payout with fees/refund, a $5.00 shortfall, a missing deposit, ambiguous split deposits, a bank-only reference, and two equal-amount rows without references. Its aggregate difference is **-$51.20**, which is not a claim of proven loss.

## Verification and limits

```sh
.venv/bin/python -m pip install -e '.[web,dev]'
.venv/bin/python -m unittest discover -s tests -v
```

The 55 tests cover exact matches, refunds/fees, discrepancies, ambiguity, malformed input, currency rejection, fabricated/reused/missing rows, invented adjustments, money precision, revision limits, replay failures, cancellation, cleanup, alternate CSV profiles, browser API boundaries, downloads, and history recovery. Controlled test doubles exercise failures; they are separate from the live River/CreateOS integration runs. See [Phase 3 validation](docs/phase3-validation.md) for actual browser verification.

The sandbox has disabled ingress, a restrictive nonempty egress allowlist, and bounded execution/output. The controller independently verifies outputs and never executes generated source. Sandbox deletion is attempted on both success and failure; failed cleanup is recorded. One local run may be active at a time. Unexpected process termination can leave a stale `.local/active-run.lock` or an owned sandbox requiring cleanup.

Postgres stores run metadata and summaries only. Inputs, code, traces, and reports stay local and ignored by Git. Use synthetic inputs for public demonstrations. Checks establish consistency with supplied data, not authenticity of external financial records or correctness on every possible future input. See [architecture and trust limits](docs/architecture.md).
