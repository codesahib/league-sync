# Workflow switching and replay recovery

## Reproduced before implementation

Against source `00abbd0` (including the unexpected-error fix `2ed281b`), the new regression executed the complete review sequence: deliver in Reliable sync, select Manual CSV, replay, process and reactivate. Before changing the implementation, it failed with:

```text
Replay returned 200
processing={'attempted': 0, 'delivered': 0, 'failed': 0, 'conflicts': 0}
reactivation=409 {'detail': 'Resolve or deliver outstanding jobs before changing workflow'}
1 failed
```

Actual command/output and exit code: [workflow-replay-red.txt](../evidence/workflow-replay-red.txt).

```bash
.venv/bin/python -m pytest backend/tests/test_workflow.py::test_reported_replay_in_baseline_sequence_cannot_deadlock -q --tb=short
```

The Windows `.venv/Scripts/python.exe` equivalent was used locally. The regression now passes.

## Root cause

Three individually reasonable rules formed a deadlock: replay accepted any delivered event regardless of workflow; processing intentionally did nothing in Manual CSV; and every workflow change rejected outstanding jobs. Replay could therefore commit pending work into a mode that could neither process it nor enable its processor.

Workflow changes and replay already use the same SQLite `BEGIN IMMEDIATE` transaction boundary. The fix uses that existing serialization, rather than adding another queue, worker or workflow state.

## Prevention and safe transitions

`backend/sync.py::replay` now checks the workflow before changing the event or appending an audit row. Manual CSV returns HTTP 409 with instructions to select Reliable sync first. Missing event IDs still return 404. Replay in Reliable sync retains the delivered-event requirement, immutable payload/key and version-based no-op behavior.

`set_workflow` still refuses to leave Reliable sync while pending, failed or conflicting jobs exist. Its 409 identifies the blocking event and tells operators to process, retry or resolve it in Reliable sync. A replay/switch race is serialized: either replay commits and the switch is rejected, or the switch commits and replay is rejected. Legitimate undelivered work stays in a processable mode.

Clean baseline-to-reliable activation still requires aligned rosters and complete team matching, then adopts the aligned copy. Recovery does not bypass those checks or rebuild mappings to conceal inconsistencies. Same-mode selection remains an idempotent no-op.

## Recovery for previously trapped replays

The existing mode selector cannot repair old persisted traps by itself. A narrow API operation is available through FastAPI's `/docs` or directly:

```bash
# Replace 1 with the event ID reported by the activation error or /api/state.
curl -X POST http://127.0.0.1:8001/api/sync/events/1/cancel-replay \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Reviewed original delivery; cancel only the legacy replay."}'

# After recovering each trapped replay, activate normally.
curl -X POST http://127.0.0.1:8001/api/workflow \
  -H 'Content-Type: application/json' \
  -d '{"workflow":"reliable"}'
```

`POST /api/sync/events/{id}/cancel-replay` requires a nonblank 8–240-character reason and all of these checks:

- Current mode is Manual CSV and the event is pending.
- The source-to-target identity map's last applied version is at least the event version.
- The event has a recorded `applied` or `duplicate_or_old_version_ignored` delivery.
- The event has a recorded `replay_requested` action.

Only then does it restore `delivered` status, clear the pending replay's scheduling/error fields, update its timestamp, and append `replay_cancelled` with the reason. That status refers to the proven original delivery, not a new delivery. Attempts, immutable payload/key/version, source/target rows, mappings and all existing audit entries are retained. No adapter is called. Failure to save the recovery audit rolls back the status change too.

Cancellation requires proof rather than treating every pending event as disposable. Unproven/original work returns 409 with an investigation instruction; invalid input returns 422 and missing events return 404. Repeating cancellation after success returns 409 without another write. In Reliable sync, the error directs the operator to process the queue instead. A baseline activation blocked by an old pending replay now gives the exact cancellation URL.

This is deliberately a duplicate-replay cancellation rather than a broad activation override. Enabling the worker against arbitrary dirty data, discarding original deliveries, or rebasing mappings would weaken revision checks and the strict per-player ordering introduced in `2ed281b`.

## Verification

`backend/tests/test_workflow.py` adds 20 cases covering the reported sequence, normal and same-mode transitions, replay in both modes, original-work switching guards, legacy recovery, each missing proof, invalid input, wrong mode, missing IDs, recovery-audit rollback, activation-mapping rollback and concurrent switch/replay serialization.

The legacy fixture writes the old endpoint's historical pending/replay-audit state directly to the isolated test DB because the fixed API can no longer produce it. The browser regression uses the same approach only for fixture setup; it verifies UI transitions and errors, API recovery, normal reactivation, unchanged League records and no browser page errors. No unsafe production fixture endpoint was added.

All 30 existing backend cases, including unexpected-error recovery, ordering, retry exhaustion and replay safety from `2ed281b`, remain in the full **50-test** backend suite. The browser suite now has **3 tests**. Run the complete existing verifier:

```bash
bash scripts/check.sh --browser-channel chrome
```

Windows equivalent executed locally: `.venv/Scripts/python.exe scripts/verify.py --browser-channel chrome`. Full output/source commit is captured in [verification.json](../evidence/verification.json). [comparison.json](../evidence/comparison.json) retains the same baseline and improved results. `baseline-demo` remains `3b9cc2eb2313c4ccd4c6e1fdb3edc47e98302e6f`.

## Limits

Recovery intentionally cannot cancel work whose prior application is unproven. Missing/corrupted identity or audit records require investigation, not a forced status update. Arbitrary externally modified mode flags with original undelivered jobs are not repaired by this narrowly scoped endpoint; supported transitions prevent that state. If multiple legacy replays exist, each needs a reviewed cancellation. Dirty rosters can still block activation after replay recovery under the existing cutover policy.

The recovery control is an API operation available in `/docs`, not a new dashboard feature. Local unauthenticated scope and SQLite transaction guarantees are unchanged. This fix does not address benchmark labels, existing-data migration or the conflict-review polling finding.
