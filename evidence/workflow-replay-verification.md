# Workflow/replay deadlock fix: verification

Implementation commit: `8c696b7` (`fix(sync): reject CSV replays and recover traps`). The complete existing verifier ran against that committed source; the subsequent evidence update contains no implementation changes.

## Before and after

Before implementation changes, the exact-sequence regression against `00abbd0` failed: CSV-mode replay returned 200, processing attempted zero jobs and reliable reactivation returned 409. The actual exit code 1 and assertion are in `workflow-replay-red.txt`.

After the fix:

```text
.venv/Scripts/python.exe -m pytest backend/tests -q
50 passed, 1 warning

PLAYWRIGHT_CHANNEL=chrome npm.cmd --prefix frontend run test:ui
3 passed, 0 skipped

.venv/Scripts/python.exe scripts/verify.py --browser-channel chrome
All 6 child commands exited 0:
  pytest + JUnit: 50 passed, 1 warning
  TypeScript / Vite build: passed
  Prettier check: passed
  npm audit: 0 vulnerabilities
  baseline/reliable benchmark: assertions passed
  Playwright / installed Chrome: 3 passed
```

Environment assignment above describes the setting; PowerShell syntax was used locally. Full commands and output are in `verification.json`; per-test results are in `backend-tests.xml` and `ui-results.json`. The warning is the existing upstream Starlette/AnyIO deprecation. Execution was on Windows; no Linux execution claim is added.

## Coverage

Twenty new backend cases cover exact-sequence reproduction, safe and idempotent mode transitions, replay in both modes, pending/failed/conflicting work, audited legacy cancellation, each missing proof, invalid recovery input, wrong mode, missing IDs, audit rollback, activation rollback and concurrent switching/replay. All 30 existing backend cases, including strict per-player ordering and unexpected-error recovery from `2ed281b`, still pass unchanged.

The new browser regression exercises normal mode changes, invalid baseline replay, refusing to disable reliable processing with pending work, an existing legacy trap fixture, the actionable error, cancellation through the API and successful normal reactivation. Target records remain unchanged and there are no browser page errors. The test fixture emulates old committed rows directly in the isolated UI test database; no production test hook was introduced.

## Unchanged measurements and tag

The benchmark JSON is byte-for-byte unchanged from before this fix:

```text
SHA256 66e1cac253e98d0b2106fe10121ac7e4a6e5b55b28e661560483241527cdcc1c
baseline-demo 3b9cc2eb2313c4ccd4c6e1fdb3edc47e98302e6f
```

Batch results remain baseline 10 mismatches / 30 League rows versus reliable 0 mismatches / 20 rows, with 10 duplicate event deliveries ignored. The two outage probes still accept 2 of 3 deliveries. The original baseline tag and source remain unchanged.

Recovery only cancels a proven already-applied pending replay in CSV mode and records a reason; it does not skip original work, write the roster or bypass cutover checks. Missing/corrupt evidence and dirty baseline rosters still require investigation. Root cause, API commands and limits: `docs/07-workflow-replay-recovery.md`.
