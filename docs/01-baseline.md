# Gate 1: working original workflow

This is an independent synthetic demonstration, not a description of a real company.

Club registrations and League eligibility records have independent tables and IDs. The initial seed contains 2 clubs, 4 teams and 20 players in each portal. Club owns name, membership and assignment. League owns eligibility.

The existing importer accepts registration snapshots keyed by `(source_ref, league_team_id)`. Repeated imports into the same team update a record rather than creating another. This is a plausible team-registration contract: importing a roster does not implicitly remove registrations in other teams. There is no global source-to-target mapping or transfer lifecycle. A transfer therefore needs manual discrepancy investigation after CSV upload; the old team registration survives. No random corruption or intentional failure is added to this production path.

## Reproduce

Follow the setup in README. Transfer Synthetic Player 01 from Cedar North to Cedar South. Club changes immediately; League remains on North. Export CSV, upload that file, inspect reconciliation: the new South registration exists alongside the old North registration. A same-team re-import alone does not cause duplicates.

`backend/tests/test_baseline.py` verifies working registration/import, independent IDs, atomic invalid-input rejection, and explicitly asserts the known transfer limitation. The limitation test is expected to pass; it documents behavior, rather than hiding a failed correctness assertion.

UI: `frontend/src/main.tsx`; CSV contract: `backend/service.py`; separate schemas: `backend/db.py`.

Commit: `baseline: working original workflow`; tag: `baseline-demo`. This gate precedes queue implementation.
