# Unexpected adapter failures: root cause and fix

## Reproduction before implementation

The review reported an event that repeatedly raises `RuntimeError` blocking unrelated work. Before changing `backend/sync.py`, a regression was added to `backend/tests/test_sync.py`: player 1's adapter always raises while player 2's valid event should deliver in the same processing call. Running the test failed with an uncaught `RuntimeError: Synthetic adapter bug` at `deliver(conn, event)`. The actual output and exit code 1 are retained in [unexpected-errors-red.txt](../evidence/unexpected-errors-red.txt).

```bash
.venv/bin/python -m pytest backend/tests/test_sync.py::test_unexpected_adapter_error_is_recorded_without_blocking_other_players -q --tb=short
```

This command was executed using the Windows `.venv/Scripts/python.exe` equivalent. An initial new test-module import failed during collection; that test setup was corrected before recording the actual failing regression. No implementation was changed until the regression reproduced the adapter exception.

## Root cause

`drain()` previously handled only `ConnectionError` and `DeliveryConflict`. Another adapter exception escaped, rolling back its outer transaction, including any attempt tracking. The lifespan worker caught it outside the processing loop, logged it and tried the same oldest pending event on the next tick. The event stayed pending at zero attempts indefinitely, starving other players without a durable failed-job record.

The old query also permitted a later version of a player to run while an earlier event was delayed. Merely catching the exception would have allowed silent bypass of that failed earlier version, violating the ordering required for this fix.

## Design decision

Keep the existing SQLite queue, statuses, retry endpoints and operator UI. No schema migration or new infrastructure is needed.

- Select a due event only if no lower source version for that player has an unresolved status. A delayed, failed/exhausted or conflicting predecessor blocks that player's newer events, regardless of the predecessor's retry eligibility. Other players remain eligible. The existing `(source_id, version)` uniqueness index supports this lookup.
- Place the adapter call inside a savepoint. On any ordinary `Exception`, roll back all target and identity-map changes before recording the failure in the outer transaction. This also covers a `ConnectionError` raised after a local target write. Fault-budget consumption remains outside the savepoint so the simulator still represents one consumed failure.
- Preserve `DeliveryConflict` as a conflict requiring explicit resolution. Other adapter exceptions become failed deliveries. Known conflict/error text stays compatible with the existing mapping resolution and UI. Unexpected errors include their exception class in `last_error` and the durable audit; server logs retain a traceback.
- Reuse the three-total-automatic-attempt budget and 2/4-second retry delays. Exhausted jobs have no automatic attempt scheduled. The existing Retry control or `POST /api/sync/events/{id}/retry` grants another attempt without clearing attempt/audit history. Correcting the adapter alone does not silently reset an exhausted budget.
- Leave immutable payloads, event keys, identity/version guards, eligibility ownership and revision approval intact. A replay of an already-applied old version remains a no-op. Later original versions now wait for earlier unresolved versions rather than relying on last-write-wins convergence.

This intentionally replaces the earlier test that permitted a newer pending version to bypass a delayed predecessor. The old-version replay regression remains; conflict tests still require authority approval and reject stale revisions. The injected post-write exception test now expects a durable failed state and explicit retry instead of an escaped exception.

## Regression coverage and operator recovery

`backend/tests/test_sync.py` now verifies:

1. A persistent `RuntimeError` for player 1 is recorded while player 2 succeeds in the same drain.
2. Automatic attempts occur only when due, stop at three, and retain committed failure state/error/audit through fresh API/database connections.
3. Player 1's next version remains pending with zero attempts during backoff and exhaustion; unrelated new work still delivers after exhaustion.
4. After the error is fixed, explicit retry applies the failed version before the next version; audit history and League eligibility survive. Replaying the recovered old event changes no target record.
5. A transient unexpected error recovers automatically when due without an operator retry.
6. Both `RuntimeError` and `ConnectionError` after target updates roll back target revisions and mappings. Failure after a new registration insert also rolls back the inserted target/mapping, so retry/replay does not duplicate it.
7. A conflict holds later versions for that player while unrelated work proceeds; stale approval and plain Retry remain rejected until the correct conflict resolution.

Failed events are already visible through `/api/state` and the delivery dashboard: status, total attempts, exception detail and audit. Inspect the error, correct the underlying adapter issue, then use Retry. Newer pending events for the same source player wait behind the failed/conflicting predecessor. There is no automatic skip or discard operation.

The backend suite passes **30 tests**. Run the complete existing gate with:

```bash
bash scripts/check.sh --browser-channel chrome
```

The Windows command used for the complete gate is `.venv/Scripts/python.exe scripts/verify.py --browser-channel chrome`. Current command output is in [verification.json](../evidence/verification.json); the benchmark remains [comparison.json](../evidence/comparison.json). Historical baseline/evaluation measurements are unchanged. `baseline-demo` remains `3b9cc2eb2313c4ccd4c6e1fdb3edc47e98302e6f`.

## Remaining limits

An exhausted event deliberately blocks subsequent versions for that player until repaired and retried. Operators cannot discard an immutable event through this patch. Pending successors use the existing UI status; no new blocked-status UI was added.

The boundary catches adapter `Exception`, not process-control `BaseException`. Database/transaction failures outside the adapter boundary, failures while persisting the error, process termination and a broken savepoint cannot promise a durable failure record; the outer transaction rolls back and the worker's existing outer error logging remains. There is no new claim of remote exactly-once delivery or abrupt process-crash testing. Persistence tests reopen API/database connections to the committed SQLite file.

The baseline-mode replay trap, benchmark labeling, migration support and conflict-review polling findings from the independent review are outside this fix and remain unaddressed.
