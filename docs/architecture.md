# Architecture

The trusted Python controller reads two small CSVs, validates their explicit USD profile, keeps original bytes, and assigns stable record IDs. River receives the matching contract, headers, and record counts. It writes a complete Python program. Raw source values are omitted from the initial model request; repair requests can contain execution/check feedback.

CreateOS EU runs the generated program in a disposable `devbox:1` sandbox. The controller transfers input copies, program, and a resource-limiting harness through the files API. It sends no River, CreateOS, or database credentials into the VM. Network ingress is disabled. A nonempty egress allowlist permits only the TEST-NET target `203.0.113.1:1`; an empty CreateOS allowlist would allow all traffic. A probe against `1.1.1.1:443` must fail before generated code runs. This is a narrow connectivity check, not a full isolation audit.

The harness caps generated Python at 20 CPU seconds, 384 MiB address space, 512 KiB per output file, and 30 wall-clock seconds; the outer command has a 40-second timeout. Output is bounded and checked for truncation. These are resource controls inside the VM. They do not make arbitrary Python safe to run in the controller or establish adversarial guarantees against every process-control escape. CreateOS supplies the VM boundary.

The controller never imports or executes generated source. It parses the returned JSON and independently checks source hashes, real row IDs, complete coverage, exact arithmetic, grouping references, statuses, and duplicate consumption. Failure feedback goes to River for at most three generated programs. Runtime/check failures are distinct from infrastructure failures. Transient inference 429 responses receive at most two bounded retries.

An accepted program runs a second time on the identical originals. Both outputs must pass the independent checker and agree after ordering normalization. The controller saves JSON/CSV evidence reports and the accepted source only after this succeeds. The sandbox is deleted on normal completion and handled failures. A failed deletion is explicitly recorded; an interrupted network call can still require operator cleanup. Auto-pause is an additional idle limit, not a substitute for deletion.

Postgres stores run metadata and summary via a free Neon resource provisioned through Stripe Projects. It does not store the original CSVs or generated source. Original inputs, programs, execution traces, reports, and events stay in ignored local `artifacts/` storage. Failure feedback can contain input-derived values, so treat artifacts as private when using real files.

## Trust limits

- Checks establish consistency with the supplied exports, not authenticity or completeness of bank/provider records.
- A correct output on one input and deterministic replay do not prove the generated program correct for every possible file. Check every result on its actual inputs.
- Shared payout references are required for attribution; the system does not infer identity from equal amounts.
- Supported grouping is one provider payout to one bank record. Several bank records for one provider payout remain ambiguous.
- Only the documented CSV profile is supported. No live Stripe payment API, automated refunds, or financial writes are performed.
- The browser app is intended for a single local user.

## Browser workspace

`settleproof serve` starts a loopback-only FastAPI server. It serves the HTML/CSS/JavaScript interface and same-origin JSON/file endpoints. Credentials are loaded only by the server. Host validation, a custom request header for mutations, an Origin check, a restrictive script CSP, no-store API responses, and bounded uploads protect the local boundary.

The run service accepts one active reconciliation and keeps the event loop free while the existing controller runs in a background thread. The original controller's filesystem lock also prevents overlap with terminal runs. Browser progress comes from actual controller events and saved manifests. Cancellation is cooperative: an in-flight model/remote request can finish before the controller stops at its next stage and cleans up. Unexpected process termination can still leave a stale lock or owned sandbox; auto-pause and recorded sandbox IDs support recovery.

Reports are exposed only for checked completed jobs. Artifact downloads use a fixed allowlist of names; arbitrary paths and configuration files cannot be requested. Generated code is displayed as escaped text and offered as an attachment, never run in the browser or controller. Failed runs retain their real attempt history without exposing an accepted report.

History merges Neon metadata with local manifests. A run stored only in Neon is explicitly marked metadata-only because its original files/code/report remain on the machine that produced it. Completed local results reopen after a fresh server process without a new model call.

The two supported header profiles are explicit semantic mappings, not inferred matches. The trusted reader validates either profile, retaining original headers in source evidence; River receives the mapping and writes the actual adapter code. The checker remains outside the sandbox and validates the same financial constraints for both profiles.
