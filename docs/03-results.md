# Gate 4: measured results

This is an independent synthetic experiment. Commands ran on Windows with Python 3.13.14 and Node 24.22.0. No human engineering-time measurement, real customer traffic, Beacon access or production comparison was performed.

## Reproduce

From an installed Ubuntu/WSL checkout:

```bash
.venv/bin/python scripts/benchmark.py --mode both
bash scripts/check.sh --browser-channel chrome
```

Use `bash scripts/check.sh` instead when Playwright Chromium is installed. Exact commands, output, exits and source revision are captured in [verification.json](../evidence/verification.json). Measurements: [comparison.json](../evidence/comparison.json). The pre-improvement observation remains [baseline.json](../evidence/baseline.json). The harness asserts reliable convergence and replay expectations, exiting nonzero on regression.

## Comparable batch

Each workflow receives a fresh seed: 2 clubs, 4 teams, 20 Club players and 20 independent League records. Transfer players 1–5 from Cedar North to South and 11–15 from Harbor East to West. Both copies have 10 mismatched players before delivery. Baseline exports the resulting 20-row snapshot, uploads it, inspects reconciliation and replays the snapshot. Reliable mode delivers 10 immutable events and replays each once. Automatic processing is paused in the harness to expose identical checkpoints; `/api/sync/process` replaces worker ticks. A separate backend test verifies automatic processing/retry without the browser.

The same source operations and correctness definition apply. A mismatch means a source player is missing, duplicated, or differs in a Club-owned field; an orphan target is also reported. A source with both stale and duplicate records counts once. League eligibility is intentionally excluded. Explicit team mappings determine assignment equivalence in reliable mode.

| Observed measure | Baseline CSV | Reliable outbox |
| --- | ---: | ---: |
| Seeded players per portal | 20 | 20 |
| Source transfers | 10 | 10 |
| Mismatched players before delivery | 10 | 10 |
| Mismatched players after delivery + replay | **10** | **0** |
| Final League records | **30** | **20** |
| Transfers represented by one correct League record | **0 / 10** | **10 / 10** |
| Accepted physical records | 40 CSV rows | 20 event deliveries |
| Duplicate event deliveries ignored by version guard | Not an event protocol | 10 |
| Defined routine handoff actions after a transfer | **3** | **0** |

The 40-row and 20-event acceptance counts have different payload units, so they are not a throughput ratio. Baseline safely repeats a same-team import; it does not randomly duplicate uploads. Its ten extra records specifically retain old team registrations after transfers.

### Operator-action methodology

The benchmark records actual dispatch of export, upload and reconciliation inspection: three coarse operator actions for the original handoff path, serving one transfer or a batch. Reliable sync needs no additional routine handoff action after a Club change. One-time activation, the shared source-side transfer, navigation, file selection, discrepancy repair and experimental replay are excluded. This is a path count, not three measured mouse clicks or a timed user study. Inspection alone does not repair baseline discrepancies, so the count understates work required for correctness. Exceptional conflict decisions still require people.

## Identical outage / retry / duplicate probe

A separate fresh 20-player seed in each mode receives one transfer (player 1 to team 2), one temporary failure before the target write, a retry and duplicate replay. The baseline harness raises a reproducible transport exception before its first CSV request; subsequent requests use the real importer. Reliable mode uses the built-in pre-write failure simulator and durable retry/replay endpoints. These are synthetic boundaries, not actual remote network traffic.

| Observed measure | Baseline CSV | Reliable outbox |
| --- | ---: | ---: |
| Delivery attempts | 3 | 3 |
| Accepted deliveries | **2** | **2** |
| Injected failures | 1 | 1 |
| Final mismatched players | 1 | **0** |
| Final League records | 21 | **20** |
| Durable failure audit entries | 0 | **1** |

Accepted delivery rate stayed **2/3**. The improvement did not remove the outage or make networking inherently more reliable. It made recovery durable and the successful result correct. Baseline's accepted payload is a 20-row CSV; the improved payload is one event. This is not a bandwidth or latency comparison.

## Quality checks and limitations

- The initial evidence run passed **24 backend tests**. Following the [unexpected-adapter-error fix](06-unexpected-adapter-errors.md), the suite passes **30**, adding durable unexpected-failure isolation, bounded recovery and strict per-player ordering. Coverage retains automatic retry with the lifespan worker, injected errors before acknowledgement, transaction rollback, competing processors, old-version replay, conflict rejection and missing-team resolution.
- **2 Playwright tests passed** in installed Chrome, covering real CSV upload and the improved workflow. Mobile width 390 has no document overflow. Screenshots: [baseline](../evidence/baseline.png), [improved](../evidence/improved.png), [failure](../evidence/failed-delivery.png), [mobile](../evidence/mobile.png).
- TypeScript/Vite build and formatting check passed; npm audit reported zero vulnerabilities. The initial older Vite advisory was corrected before baseline tagging.
- One upstream Starlette/AnyIO deprecation warning remains. The Chromium download failed with ENOSPC; the UI gate subsequently passed in Chrome. No failed test is described as passing or skipped.
- Small deterministic samples, no statistical confidence interval, load-test claim or published latency metric. Harness durations are not human effort saved.
- Local target writes and acknowledgements share a transaction. Remote delivery guarantees have not been tested. Ubuntu/WSL instructions are provided; this execution used Windows equivalents.
