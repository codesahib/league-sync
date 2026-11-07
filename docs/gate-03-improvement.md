# Gate 3: implemented and verified improvement

The baseline and diagnosis were committed before these changes. This gate adds `backend/sync.py` and integration-owned tables in `backend/db.py`. Club writes call `enqueue` inside their transaction. Events contain immutable source snapshots and version keys; the League adapter updates a mapped target only after checking its field revision. Eligibility is excluded from those writes.

The lifespan worker polls independently of the browser. Failed deliveries have bounded automatic retries; exhausted jobs remain available for operator retry. Revision conflicts need a reason and the exact reviewed target revision. Missing team mappings have a separate explicit resolution. A local failure simulator rejects before the League write, and replay uses the same event key. Audit records remain after success.

`frontend/src/operations.tsx` exposes status, replay, retry, failure simulation, conflict comparison and authority approval. `frontend/src/main.tsx` keeps the original CSV workflow visible and adds the server-backed mode selector. Activation requires aligned rosters; CSV writes cannot bypass reliable mode. Additional teams and mappings are working forms, not placeholders.

Before the improvement commit, the following were executed successfully:

- Backend suite: **24 passed**, one upstream deprecation warning.
- Frontend TypeScript + Vite build: passed.
- Playwright: **2 passed**, using installed Chrome. Tests cover the real CSV file upload, queue failure/retry, replay, conflict review, audit, and mobile overflow.
- The backend suite includes a real lifespan-worker test: no browser and no process endpoint, one transient failure, eventual correct delivery on attempt 2.

Screenshots were inspected at desktop and mobile sizes. All visual data is synthetic. Benchmark evaluation and handoff follow this commit.
