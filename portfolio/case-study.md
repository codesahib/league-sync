# AI-Assisted Integration of Two Legacy SaaS Workflows: From Manual Roster Reconciliation to Reliable Synchronization

**Independent, synthetic, portfolio-company-inspired demonstration.** This has no connection to Beacon production systems, real customers or an actual acquired company's code.

## Existing process and bottleneck

A Club Portal registers players and records transfers. A League Portal maintains separate identifiers and eligibility records. Staff export Club CSVs, upload to League and inspect discrepancies. The importer treats rows as registrations within a team: repeated assignments work, but transfers can retain the old registration alongside the new one.

The working baseline was committed as `baseline: working original workflow` and tagged `baseline-demo` before improvement. A reproducible experiment with 20 synthetic players and ten transfers left ten mismatched players and thirty League records after upload and replay. Both uploads accepted every row. Successful delivery did not imply correct business state.

## Engineering intervention

Codex served as an engineering tool: it examined requirements, baseline schemas, import/API contracts, tests, audit output and UI screenshots. The repository initially contained only the task, so this demonstrates discovery and improvement of a constructed legacy boundary, not reverse engineering of production code.

The improvement is deterministic. A Club change atomically writes a versioned event. A worker uses stable player/team mappings to update the existing League record. Versions make duplicate/older events harmless. Target revisions block conflicting edits. Failures remain visible, retry within a bound and retain audit history. League eligibility remains League-owned.

The React dashboard shows both workflows, independent rosters, live reconciliation, jobs, retry/replay controls and explicit conflict review. New registrations, teams and mappings are working operations. No chatbot, paid API or runtime model is involved.

## Verified result

Both workflows receive fresh identical seeds, ten fixed transfers, delivery and complete duplicate replay.

| Measure | Original CSV | Improved sync |
| --- | ---: | ---: |
| Mismatched players after replay | 10 | **0** |
| League records for 20 source players | 30 | **20** |
| Correctly represented transfers | 0 / 10 | **10 / 10** |
| Additional routine handoff actions after a source change | 3 | **0** |

The action path is export, upload and inspect. It excludes navigation, file selection, source editing, one-time activation and discrepancy repair. It is not a human timing study. A separate transfer/outage/retry/replay probe accepted **2/3 deliveries in both workflows**. Improved sync converged and retained a durable failure audit; CSV retained one inconsistent player. Network failure itself did not improve.

The initial final gate passed 24 backend tests. Following the [unexpected-adapter-error fix](../docs/06-unexpected-adapter-errors.md), the current gate passes **30 backend tests, 2 browser tests, typecheck/build and formatting**. npm audit reported zero vulnerabilities. Tests cover replay, old versions, competing processors, rollback, background retry, missing mappings, stale authority approval, unexpected-failure isolation and strict per-player ordering. Screenshots and raw command outputs are retained. Validation ran on Windows; Ubuntu/WSL setup is documented but was not executed here.

## Handoff and limits

The handoff includes deterministic reset, locked dependencies, baseline history, executable comparison, field ownership, a demo script and operating guidance. A small team can extend the target adapter while preserving contract/reliability tests.

Club and League own separate SQLite records. Local target transactions do not establish distributed exactly-once delivery. Real identity migration, remote idempotency, access controls, tenancy and scale need further work. Human review remains necessary for business conflicts. No elapsed engineering time or human-only comparison was measured; no AI productivity percentage is claimed.

## Evidence

- [Baseline](../docs/01-baseline.md), [diagnosis](../docs/02-diagnosis.md), [results](../docs/03-results.md)
- [Raw comparison](../evidence/comparison.json), [actual verification output](../evidence/verification.json)
- [AI engineering decisions](../docs/04-ai-engineering-process.md)
- [Implementation](../backend/sync.py), [regression tests](../backend/tests/test_sync.py), [browser test](../frontend/tests/smoke.spec.ts)
- [Quickstart](../README.md), [tradeoffs](../docs/05-tradeoffs.md), [demo](../docs/demo-script.md)
- [Baseline screenshot](../evidence/baseline.png), [improved](../evidence/improved.png), [failure](../evidence/failed-delivery.png), [mobile](../evidence/mobile.png)
