# Unexpected adapter failure fix: verification

Code commit: `2ed281b` (`fix(sync): isolate adapter failures by player`). The complete verifier ran against that committed source, with no uncommitted implementation changes. This evidence update changes reports/screenshots only.

## Executed checks

Before implementation changes:

```text
python -m pytest backend/tests/test_sync.py::test_unexpected_adapter_error_is_recorded_without_blocking_other_players -q --tb=short
1 failed: RuntimeError: Synthetic adapter bug
```

Exact captured output: `unexpected-errors-red.txt`. The implementation was unchanged when that regression failed.

After implementation:

```text
.venv/Scripts/python.exe -m pytest backend/tests -q
30 passed, 1 warning

.venv/Scripts/python.exe scripts/verify.py --browser-channel chrome
All 6 child commands exited 0:
  pytest + JUnit: 30 passed, 1 warning
  TypeScript / Vite build: passed
  Prettier format check: passed
  npm audit: 0 vulnerabilities
  baseline/reliable benchmark: assertions passed
  Playwright / installed Chrome: 2 passed, 0 skipped
```

Full command output/source identity: `verification.json`. Test reports: `backend-tests.xml` and `ui-results.json`. The warning is the existing upstream Starlette/AnyIO deprecation. Validation used Windows; no new Linux execution claim is made.

## Benchmark and baseline preservation

`comparison.json` is byte-for-byte unchanged before/after this fix:

```text
SHA256 66e1cac253e98d0b2106fe10121ac7e4a6e5b55b28e661560483241527cdcc1c
```

The same 20-player, 10-transfer batch still yields baseline 10 mismatches / 30 League rows, reliable 0 mismatches / 20 rows and 10 duplicate event deliveries ignored. Both outage probes still accept 2 of 3 deliveries; the improved probe retains its durable failure audit and correct result. These measurements are separate fresh-seed outcomes, not a cleanup of the baseline database.

`baseline-demo` is unchanged at `3b9cc2eb2313c4ccd4c6e1fdb3edc47e98302e6f`.

## Coverage and limitations

The added/updated tests cover persistent unexpected errors without cross-player starvation; three-attempt exhaustion and committed state; delayed/pending/conflicting predecessor ordering; automatic and explicit recovery; rollback of updates and inserts; and safe old-event replay after recovery. An earlier test expecting pending versions to bypass one another was updated to the user's required ordering rule. A post-write exception test now expects durable failure rather than an escaped exception and covers both RuntimeError and ConnectionError.

An exhausted predecessor intentionally holds that player's later events until repaired/retried. Transaction/storage failures that prevent saving the error and process termination remain outside the adapter exception guarantee. Existing unrelated review findings were not addressed. See `docs/06-unexpected-adapter-errors.md` for the root cause and operational procedure.
