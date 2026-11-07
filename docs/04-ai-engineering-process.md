# Gate 5: AI-supported engineering process

The operational starting point was a Club CSV export, a separate League import and manual reconciliation. The engineering task was to discover why a valid transfer did not converge, preserve working registration behavior and leave a testable integration. Codex acted as a coding agent throughout this session; the product does not call a model.

## What the agent actually examined

The initial repository contained only `TASK.md` and Git metadata; there was no acquired production code to reverse-engineer. Codex read the task in full, inspected status/history, checked Python/Node/npm availability and built the requested realistic baseline first. It then examined that baseline's contracts and observed test outputs. This simulates learning an integration boundary; it does not claim to audit a real company.

| Evidence inspected | Finding and action |
| --- | --- |
| `TASK.md`, initial file listing, empty Git history | Establish a working original phase, immutable baseline tag and evidence before improvement. |
| `backend/db.py` | Club IDs 1–20 and League IDs 1001–1020 are independent. Target uniqueness is scoped to source reference plus team. Mapping belongs to the integration. |
| `backend/service.py::import_csv`, `export_csv`, `reconcile` | Team snapshots do not express deregistration; removing absent players on upload would be unsafe. Preserve the importer; add a separate reliable path. |
| `backend/tests/test_baseline.py`, `evidence/baseline.json` | Repeat imports work, but ten transferred players remain inconsistent. Delivery acceptance is insufficient correctness evidence. |
| `backend/app.py` Club-write transactions | Outbox insertion must share the authoritative change's transaction. Browser-driven processing would miss unattended work. |
| `backend/sync.py`, `backend/tests/test_sync.py` | Check mapping constraints, version/revision guards, rollback, retry bounds and competing processors. |
| npm audit, build logs, Playwright output, desktop/mobile PNGs | Replace affected Vite release; use Chrome after ENOSPC; isolate UI-test ports after discovering an existing process on 5173. |

Official references consulted: [Python sqlite3 transactions](https://docs.python.org/3/library/sqlite3.html) and [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/). The code uses explicit transactions and a managed worker lifecycle; tests provide repository-specific evidence.

## Proposals and engineering review

“Review” here means the agent's design/self-review against the task and executable tests. There was no separate human reviewer or fabricated team sign-off. The user authorized routine implementation choices; this does not claim they personally selected these designs.

| Proposal | Decision and reason |
| --- | --- |
| Runtime LLM infers identity or resolves updates | Rejected: identity, ordering and authority must be reproducible. No indispensable language-model problem exists here. |
| Reuse Club rows as League data | Rejected: hides the boundary and independent ownership. |
| Delete League rows absent from each CSV | Rejected: partial/team snapshots do not prove removal. |
| Broker / microservices | Rejected for this local scope: SQLite already supplies durability and serialized transactions. |
| Global player map and explicit team map | Accepted: transfers update the same League identity; uniqueness exposes ambiguity. |
| Atomic Club change plus event | Accepted; injected enqueue-error test verifies neither write commits. |
| Blindly overwrite League conflicts | Rejected: revision mismatch stops delivery; approval needs a reason and the reviewed revision. |
| Mirror League eligibility from Club | Rejected: League owns it; preservation is tested. |
| Infinite retry / erase attempts on manual retry | Rejected: three automatic attempts; explicit retry retains history. |
| Activate against dirty ambiguous baseline data | Rejected: aligned-copy cutover is required. Real migration needs reviewed identity cleanup. |
| Report machine timings as saved engineer hours | Rejected: only action counts, correctness and delivery outcomes were measured. |

Review found that matching team codes alone is insufficient after an operator intentionally maps differently coded teams. Reconciliation now uses reliable mappings; the missing-team test asserts zero mismatches after resolution. Input review added rejection of blank CSV names, unexpected columns and noncanonical source references. Frontend API/types were extracted into separate modules to remove a dependency cycle and simplify maintenance.

## Specific changes and validation

`backend/db.py` adds `sync_settings`, `team_map`, `identity_map`, `sync_events` and `sync_audit`. `backend/app.py` enqueues Club writes, manages the worker, validates operations and blocks CSV imports during reliable mode. `backend/sync.py` handles snapshots, guards, retries and audit. `frontend/src/operations.tsx` exposes delivery outcomes and explicit decisions. Reset, benchmark and verification scripts make the operational workflow repeatable.

The baseline had five backend tests and one browser test. The final suite has 24 backend tests and two browser tests; output is retained in `evidence/`. This describes coverage, not productivity. Development time, prompt count, model token usage and a human-only control group were not measured.

## Automation, AI contribution and human work

**Ordinary deterministic automation:** validation, CSV parsing, transactional writes, event keys, stable maps, version/revision guards, bounded retry, reconciliation and test execution. All run without a model or hosted AI.

**AI-assisted development:** translating requirements into the baseline, inspecting contracts and failures, proposing the design, implementation, regression generation, investigating tooling failures, screenshot review and drafting the handoff. Artifacts demonstrate the work; no causal time-savings percentage is claimed.

**Human responsibility:** confirm business field ownership and remote API contracts, validate migration matches, decide conflicting edits, authorize deployments/access controls, review code/dependencies and determine real organizational fit. The demo exposes explicit conflict approval instead of substituting a model's judgment.

## Small-team continuation

Keep original-contract tests when adding an adapter. Add the outbox write inside each new Club-change transaction and test rollback. For each new mirrored field, document ownership and add conflict/preservation coverage. Run `bash scripts/check.sh` before handoff. Preserve failed-job evidence before retry/reset. Replace the local adapter only after the remote system has a stable identity/idempotency contract; add contract tests before enabling it.
