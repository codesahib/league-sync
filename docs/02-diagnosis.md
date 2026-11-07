# Gate 2: diagnosis before improvement

Baseline tag: `baseline-demo` (`3b9cc2e`). Original source is preserved; nothing in that tag depends on the later queue.

## Observations

Executed `.venv/Scripts/python.exe scripts/benchmark.py --mode baseline` against a temporary SQLite database. See `evidence/baseline.json`. Starting from the deterministic 20-player copy, transfer players 1–5 to Cedar South and 11–15 to Harbor West. Export all 20 records, import once and replay that same export once.

- Before delivery: **10 mismatched players**.
- Both imports accept all 20 rows: **40 accepted record deliveries**.
- After duplicate replay: **30 League records**, **10 mismatched players**, **0/10 transfers represented by exactly one correct League record**.
- Defined operator path after one source-side transfer: export, upload, inspect = **3 manual handoff actions**. This excludes selecting a file, navigating and repairing discrepancies. It is an executable path count, not a human usability study or time estimate.

## Cause and test boundaries

`backend/db.py` scopes League uniqueness to `(source_ref, team_id)`; IDs differ across systems. `backend/service.py::import_csv` does not implement deregistration or a persistent player mapping. Removing assignments not present in an upload would be unsafe for partial/team-specific CSV exports. The Club write and manual handoff have no durable delivery relationship. The baseline has atomic CSV validation but no per-change delivery status, replay key or repair queue.

`backend/tests/test_baseline.py` documents the expected team-scoped behavior and the known transfer shortcoming separately. Do not change those assertions to pretend the original importer supported transfers.

## Engineering target (not yet a result)

Use an atomic Club change + SQLite outbox, explicit team mapping, one-to-one player mapping, immutable versioned events and guarded League writes. Aim for 0 reconciliation mismatches and exactly 20 target records after the same 10 transfers and replay. Routine successful handoffs should require 0 additional operator actions after the Club transfer. A temporary delivery failure must leave a durable visible job, then succeed on bounded automatic retry or explicit retry without duplicate players. Conflicting League edits must block with an actionable error, preserve eligibility, and require a recorded human decision.

No runtime LLM or external broker is needed. This is a deterministic identity/delivery problem. A single SQLite transaction can safely represent the local simulated boundary; real remote systems would need a target idempotency contract.
