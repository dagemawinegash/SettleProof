# SettleProof

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-2E7D32)](https://github.com/dagemawinegash/SettleProof/pulls)

Compare payment records with bank deposits and see what needs checking.

SettleProof uses an AI agent to write Python, runs it in an isolated CreateOS sandbox, and independently checks the result against the original CSVs. The local browser app explains differences and shows the records behind each calculation.

- Account for documented fees and refunds.
- Find mismatched amounts, missing deposits, and unclear references.
- Inspect generated code, execution evidence, and downloadable reports.

## Run locally

Requires Python 3.11+, River and CreateOS API keys, and a Postgres database for run metadata. [Configure credentials with Stripe Projects](docs/local-setup.md) first.

```sh
git clone https://github.com/dagemawinegash/SettleProof.git
cd SettleProof
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"
python -m settleproof serve
```

On Windows, create the environment with `python -m venv .venv` and activate it with `.\.venv\Scripts\Activate.ps1`.

Open **http://127.0.0.1:8000**. Choose **Compare files**, **Load samples**, then **Reconcile files** to try the synthetic examples. Starting a comparison uses your River and CreateOS credits.

The app runs locally for one user. Original files, generated code, and reports stay in the ignored `artifacts/` directory; Postgres stores run metadata and summaries.

## How it works

1. Validate the two CSVs and preserve their original records.
2. Ask River to generate a reconciliation program.
3. Run the program in a disposable CreateOS sandbox.
4. Independently verify exact amounts, references, and complete row coverage. Failed programs can be revised within a three-attempt limit.
5. Run an accepted program again and check that both results agree.

Matches require shared payout references. Differences are items to investigate, not proof of lost money. See [input formats](docs/input-format.md) and [architecture](docs/architecture.md) for details and limits.

## Command line

```sh
python -m settleproof run fixtures/demo/payments.csv fixtures/demo/bank.csv
python -m settleproof replay artifacts/YOUR_RUN_ID
```

Replay executes saved code in a new sandbox without another model call.

## Development

```sh
pip install -e ".[web,dev]"
python -m unittest discover -s tests -v
```

The interface uses plain JavaScript and CSS with a bundled Motion dependency. To rebuild that bundle, run `npm ci` and `npm run build:motion`.

Issues and pull requests are welcome. Include a small synthetic example for reconciliation bugs, and run the tests before submitting a change.
