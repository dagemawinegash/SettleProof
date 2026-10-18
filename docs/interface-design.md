# Phase 3 interface direction

The product is a local browser application for investigating payout discrepancies. Preserve the working Python controller and keep credentials on the server.

## References inspected

- [Modern Treasury reconciliation](https://www.moderntreasury.com/journal/manual-reconciliation-for-expected-payments): inspected public workflow documentation and downloaded/viewed its record-detail screenshot. Carry forward a selected financial record next to its related source records. Do not copy adjustment controls: SettleProof cannot edit source amounts to force a match.
- [Linear's interface refresh](https://linear.app/now/behind-the-latest-design-refresh): inspected its discussion of hierarchy, subdued navigation, softer dividers, and warm neutral colors, and downloaded/viewed its comparison screenshot. Carry forward compact navigation and a dominant working area.
- [TailAdmin source](https://github.com/TailAdmin/free-react-tailwind-admin-dashboard): inspected AppLayout, BasicTableOne, and Badge implementations, and downloaded/viewed its public interface preview. Carry forward responsive layout, overflow handling, aligned tables, and semantic status variants. Implement original markup/styles without importing template assets or code.

Use original CSS and browser JavaScript, served by the existing Python application. A small purpose-built interface avoids a second build/runtime while the trusted backend remains intact.

## Visual and interaction contract

Warm white canvas, ink text, forest-green actions, amber investigation states, restrained dividers, aligned tabular numbers. A compact left navigation contains workspace and run history. The working screen has three financial summaries, a checked-source strip, a filterable settlement ledger, and a selected item's evidence panel.

Show exact arithmetic and source records for the selected payout. Distinguish discrepancies, missing deposits, ambiguous deposits, bank-only references, and unreferenced records. Never label aggregate differences as established loss.

Upload dialog accepts two bounded CSV files and offers clearly marked synthetic sample files. The user explicitly starts the real run. Show actual generation, execution, checking, revision, replay, and cleanup events, with cancellation at the next safe stage. The technical evidence view exposes real attempt source, feedback, execution, and verification. Downloads include checked reports, original inputs, and the accepted program.

History comes from Neon run metadata with local artifact availability indicated. It survives an application restart. Files, code, and source-row reports remain in ignored local storage.

## Incremental implementation checkpoints

1. Reference research and interaction specification.
2. Browser API and one-job service foundation.
3. Original responsive application shell.
4. CSV upload, validation, and real run start.
5. Live progress and safe cancellation.
6. Financial summary and filterable settlement ledger.
7. Source evidence and exact arithmetic inspection.
8. Actual execution inspector and artifact downloads.
9. Persistent history and explicit alternate column profile.
10. End-to-end verification, accessibility/responsive fixes, documentation.

Commit each coherent step, preserving history. Do not rewrite previously published Phase 1/2 commits.
