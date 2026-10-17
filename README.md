# SettleProof

SettleProof is an agent that writes and runs Python to compare payment-provider exports with bank deposits and explain discrepancies using source-row evidence.

Built for the CreateOS × Stripe Projects hackathon, October 17, 2026.

## Initial scope

- Upload two CSV files: payment transactions and bank deposits.
- Generate comparison code for the supported input formats.
- Execute generated code in a CreateOS Sandbox and repair execution errors using checked feedback.
- Report matched transactions, documented adjustments, and unresolved differences.
- Export the reconciliation report and generated program.

The prototype will initially support one currency and small datasets. Ambiguous matches remain unresolved for review.

## Stack

- CreateOS Sandbox for generated-code execution.
- Stripe Projects for service provisioning and credential management.
- River for model inference, subject to verified account/model access.

## Status

Repository setup is complete. Application implementation is in progress; runnable setup instructions will be added as the first working flow is completed.

## Credentials

Keep credentials and private input data outside version control. Local service state, environment files, uploads, and generated run artifacts are excluded by `.gitignore`. Use synthetic data for public examples and recordings.
