# Baseline gate execution

Executed locally on Windows, Python 3.13.14 / Node 24.22.0:

- `.venv/Scripts/python.exe -m pytest backend/tests -q`: **5 passed**, 1 upstream Starlette/AnyIO deprecation warning.
- `.venv/Scripts/python.exe -m backend.seed`: 2 clubs, 4 teams, 20 Club players and 20 independent League records.
- `npm.cmd --prefix frontend run build`: TypeScript and Vite build passed (Vite 7.3.7).
- `npm.cmd --prefix frontend install --save-dev --save-exact vite@7.3.7`: audit reported **0 vulnerabilities**. Initial Vite 7.2.2 audit reported a high advisory, fixed before this gate.
- `PLAYWRIGHT_CHANNEL=chrome npm --prefix frontend run test:ui` (PowerShell environment syntax used): **1 passed**, including transfer, actual file upload, reconciliation and no browser page errors. Screenshot: `baseline.png`.

Initial browser installation (`npm.cmd --prefix frontend exec -- playwright install chromium`) failed with ENOSPC. Retried the test successfully using installed Chrome. Initial test server attempt collided with an existing frontend on 5173. Dedicated UI test ports are now 5183 / 8011, without touching the existing process. These are environment issues, not hidden test passes.

The baseline gate was validated before queue implementation. Full raw Playwright JSON is in the baseline tag's `evidence/ui-results.json`.
