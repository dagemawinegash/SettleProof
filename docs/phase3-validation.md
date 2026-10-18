# Phase 3 validation

Verified locally on October 17, 2026 with WSL Python 3.14, the existing River/CreateOS credentials managed through Stripe Projects, free Neon Postgres, and headless Microsoft Edge on Windows.

## Actual browser run

Run `sp-20261017T205941-1750d812` was started through the browser file-import dialog using the synthetic renamed-column samples. The server recognized the alternate profile; GLM-5.3-Flash generated Python that read the actual headers. Attempt 1 passed independent checks. The generated program executed and replayed in CreateOS EU; the controller confirmed sandbox deletion. Metadata was saved and read back.

The checked result contained 7 payment rows and 6 bank rows: expected net 51,470 USD cents, bank deposits 46,350 cents, and aggregate difference -5,120 cents. Its six investigation items include a 500-cent shortfall, a missing deposit, an ambiguous split payout, a bank-only reference, and two unreferenced rows. The difference is not characterized as proven loss.

Artifacts and browser screenshots stay in ignored local storage, not the public repository. The first Phase 1 run's genuine revision and another run's exhausted three-attempt budget remain available in history; the interface does not synthesize revisions.

## Browser checks

- Loaded an existing checked report and verified the actual totals.
- Searched payouts, switched all/review/matched filters, and navigated rows with arrow keys.
- Verified the documented fees/refund calculation and expanded original CSV fields.
- Opened the actual generated program and independent-check outcome.
- Downloaded the checked CSV as an attachment and inspected its discrepancy rows.
- Rejected malformed CSVs before run start; recognized renamed-header synthetic files.
- Started the real agent from the browser and observed live progress through the checked result.
- Reopened the result and Neon-connected history after a complete server-process restart.
- Inspected three real rejected attempts from an earlier failed run.
- Checked desktop (1512px), tablet (1024px), and phone (390px) layouts; no document-level horizontal overflow or application JavaScript errors were observed. The ledger uses its own horizontal scroll region on small screens.
- Inspected phone import controls, fixed the sample-selector spacing, and verified dialog width/controls.

## Automated checks

55 tests pass. New coverage includes browser request-origin boundaries, bounded uploads, invalid-currency rejection, artifact allowlists, rejected/stale report export prevention, restart persistence, remote-only history availability, cooperative cancellation cleanup, and both explicit CSV profiles. JavaScript syntax and Git whitespace checks also pass.

These checks cover the intended local prototype. They are not a public deployment, an exhaustive security audit, or proof that an arbitrary future generated program will pass. Every real run still goes through independent checking and a bounded attempt budget.

## Simplified interface revision

The subsequent interface revision replaces the dense ledger and permanently visible evidence panel with three plain-English issue cards, optional additional cards, collapsed totals, and a detail drawer. Original source rows, calculations, execution evidence, and downloads remain available on request. Motion is bundled locally for entry, list, category, and dialog transitions.

Browser checks against the existing checked standard-profile report confirmed the $5 discrepancy, missing references, $174 matched payout and refund evidence, search/filter behavior, preserved search after history navigation, keyboard focus restoration, code inspection, CSV download, sample validation, and malformed-file rejection. Desktop (1512px) and phone (390px) had no page-level horizontal overflow or JavaScript errors. A live drawer animation was observed; a separate reduced-motion browser context had zero running animations, including the dialog backdrop.

Browser-only test doubles verified the active progress layout, unchanged polling preserving the rendered view, and the fully matched default category. These checks started no new inference calls or CreateOS sandboxes. The existing 55 automated tests passed again after this revision. Updated screenshots are kept privately under `.local/browser/simple-*.png`.

## Submission deployment verification

On October 18, the actual public CreateOS Sandbox viewer returned HTTP 200 at `https://01m565k4rjaynk2pnnb5pm0gjn-8000.app.sb.createos.sh`. Headless Edge verified its real saved report, $5 discrepancy, expandable calculation, accepted generated code and replay evidence, CSV attachment download, desktop and 390px phone layouts, and absence of JavaScript errors. Write requests returned 403, unrelated run IDs and private file paths returned 404. No new model call or reconciliation was simulated by this deployment check.

The full hosted entry point was separately verified locally: owner login, HttpOnly session cookie, upload/sample validation, and public/private evidence boundaries. All 59 automated tests passed. The normal CreateOS application platform built successfully but served 503 with empty runtime logs; the published fallback is explicitly a credential-free, read-only viewer rather than a live owner workspace.
