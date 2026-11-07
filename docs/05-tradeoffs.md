# Tradeoffs and operational handoff

## Boundaries and guarantees

Club and League share a SQLite file for this local lab, but own separate tables, rows and identifiers. League records do not reference mutable Club player rows. Integration-owned mappings link the independent records. Reconciliation compares copies; it does not make them the same storage object.

`BEGIN IMMEDIATE` serializes processors. A source write and event commit together; a target write, mapping update, audit and acknowledgement also commit together. An interruption inside either transaction rolls it back. Unique event keys and last-applied source versions prevent replay from creating a target or reverting a later assignment. Tests exercise rollback and two competing processors.

This is **not distributed exactly-once delivery**. A real target cannot share the transaction. Its API needs an idempotency key with atomic target-side deduplication, or an inbox/receipt protocol. Production adapters also need timeouts, error classification and contract tests. No real remote latency, outage or delivery guarantee has been measured.

## Ownership and cutover

| Data | Authority | Handling |
| --- | --- | --- |
| Name, membership, assignment | Club | Mirrored from versioned snapshots |
| League eligibility | League | Integration never writes it |
| Player/team mappings | Reviewed integration configuration | One-to-one constraints; explicit mapping for new teams |
| League edit to a Club-owned field | Human review | Revision blocks delivery; approving Club authority requires a reason and reviewed revision |

Activation adopts only an aligned copy. Team codes identify matching seed teams at cutover; subsequent explicit mappings permit differently coded teams. Ambiguous baseline data needs real migration cleanup. This demo uses reset between comparisons instead of unsafe duplicate deletion. Eligibility remains local even when membership is inactive; a joint participation policy is outside this synchronization slice.

Transfers stay inside a club. APIs never delete/recycle player identities. Cross-club moves, merges, deletion, bulk reconciliation repair and retention require business rules. Registration/team creation work; team renaming and whole-team migration are outside this narrow slice.

## Failure handling

Simulated transient failures occur before target writes. Automatic retries occur after 2 and 4 seconds, for three total automatic attempts. After the third failure, jobs remain visible for investigation and explicit retry. Manual retry retains attempts; after budget exhaustion, each manual retry grants one further attempt. Conflicts never auto-resolve. A missing-team conflict returns to pending after an explicit mapping; target-field conflicts need authority approval. Stale target revisions reject approval.

Each job has its own transaction, so other due jobs can proceed despite a failure. A newer event can deliver before an earlier delayed event; the version guard makes the eventual older delivery a no-op. Unexpected worker exceptions are logged and leave committed pending work recoverable. The outage simulator is a lab control, not a real network test.

The audit is append-only through application operations, not tamper-proof: someone with SQLite file access can edit it. Reset deletes demo history. Preserve evidence before reset. UI lists cap at 100 events and 200 audit entries; counts use the full database. Production needs pagination, retention, backups and alerts for old or exhausted jobs.

## Operations

1. Start with locked dependencies and the deterministic seed. Bind to loopback.
2. Understand field ownership and mappings before cutover; do not mix CSV writes into reliable mode.
3. Inspect failures, conflicts, reconciliation and audit before retry/approval.
4. Stop interactive servers before reset. Test servers own separate ports/database.
5. Run the verifier after changes. Preserve the baseline tag as the original contract.

The unauthenticated local demo has no tenant isolation, secrets, real identities, payments or notifications. Real deployment needs those controls. Package installation uses internet; runtime assets/APIs are local. Evidence ran on Windows; Linux execution is unmeasured. One dependency deprecation warning remains; test an updated FastAPI/Starlette/AnyIO combination before making warnings fatal in CI.
