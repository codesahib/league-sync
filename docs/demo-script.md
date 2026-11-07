# Demo script

Present this as an independent synthetic demonstration inspired by acquired registration SaaS businesses. Do not describe it as Beacon production work. Lead with the operator's process.

## Prepare

Follow README setup. Stop servers, run `bash scripts/reset-demo.sh`, then start both servers. For control over each delivery, start the backend with `SYNC_AUTORUN=0 bash scripts/run-backend.sh`; otherwise processing is automatic. Open http://127.0.0.1:5173. All 20 synthetic records should reconcile despite different IDs.

## 1. Original operating process

“Club records registration; League maintains its own eligibility copy. Staff export, upload and inspect discrepancies.”

In Manual CSV, transfer Synthetic Player 01 to Cedar South. Club changes; League remains on Cedar North. One player mismatches. Export the CSV and upload that downloaded file. Reconciliation shows stale/duplicate assignments and 21 League records. Upload it again: same-team keys prevent further duplication, but the old North registration survives.

Show `docs/02-diagnosis.md` and `baseline-demo`. Explain the team-registration contract: deleting absent records on partial upload would be unsafe.

## 2. Reliable propagation

Stop servers, reset, restart. Select Reliable sync before changing anything; activation maps the aligned copy's 20 identities. Make the same transfer. Wait for the worker, or click Process queue in paced mode. Existing League record #1001 moves to South. League still has 20 records and zero mismatches.

Replay the delivered event and process/wait. The audit records “duplicate or old version ignored”; no new identity or second target revision is created. Show the mapping count and event key.

## 3. Failure and recovery

Use paced mode so automatic retry does not finish while explaining the screen. Click Fail next delivery. Transfer the player back to North and Process queue. The job fails visibly; League retains the previous assignment. Inspect the failed audit entry.

Click Retry, then Process queue. The same job succeeds on the next attempt; reconciliation returns to zero. Failed/retry/applied audit entries remain. In automatic mode, wait at least two seconds to observe automatic retry instead. Manual processing is a demonstration aid, not an ordinary handoff requirement.

## 4. Human conflict decision

Toggle that player's League eligibility to On hold. Click Simulate conflicting name for the selected player, emulating a legacy League edit to a Club-owned field. Transfer the player again and process/wait. A conflict preserves the local edit.

Expand Review conflict & approve authority. Compare source snapshot and current target name/team/revision. Enter a reason such as “Reviewed synthetic registration; Club owns roster fields.” Approve Club fields, then process/wait. Reconciliation reaches zero; eligibility remains On hold. A changed target revision would invalidate stale approval. A model does not choose which business edit wins.

## 5. Optional: teams and missing mapping

Expand Manage teams & explicit mappings. Create a Cedar Club team (Cedar Reserve, code CR) and a separate League team (League Reserve, code LR). Transfer a Cedar player to the new source team. Processing blocks for a missing mapping. Select the new source/target, save the mapping and process/wait. Different codes work after explicit mapping.

Register a new synthetic player to demonstrate creation of a mapped League identity. Never enter real person information.

## 6. Evidence

Run `.venv/bin/python scripts/benchmark.py --mode both`; temporary databases keep the interactive demo unchanged. Show `evidence/comparison.json`: 10 → 0 mismatches, 30 → 20 target records, ten duplicate event deliveries ignored. Defined additional handoff actions: 3 → 0. Both modes accepted two of three deliveries in the outage probe; the claim is durable recovery and correct convergence.

Show `docs/04-ai-engineering-process.md`: Codex inspected contracts, proposed mapping/queue design, implemented it and exercised edge cases. There is no runtime AI. The gate passes 24 backend and two browser tests. No human engineering-time savings or production impact was measured.

Finish with the maintainable scope: a small SQLite service and testable adapter. Remote idempotency, reviewed identity migration and real access controls remain future work. Reset afterward if a clean start is needed.
