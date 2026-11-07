# League Sync Reliability Lab

Independent, synthetic, portfolio-company-inspired case study. Working Club and League portals with a manual CSV handoff. No credentials, AI service or production data required.

## Ubuntu / WSL setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
bash scripts/reset-demo.sh
```

Terminal 1: `.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001`

Terminal 2: `npm --prefix frontend run dev`

Open http://127.0.0.1:5173. Run `.venv/bin/python -m pytest backend/tests` and `npm --prefix frontend run build`.

UI smoke: `npm --prefix frontend exec -- playwright install --with-deps chromium`, then `npm --prefix frontend run test:ui`. The test owns ports 5183 / 8011 and a separate `data/ui-test.sqlite3`. If Chrome is already installed, use `PLAYWRIGHT_CHANNEL=chrome npm --prefix frontend run test:ui` instead of installing a browser.

Ports: backend 8001 and frontend 5173. SQLite defaults to `data/demo.sqlite3`; set `LEAGUE_DB` to override. Work through export, CSV upload and reconciliation in the UI. Reset while servers are stopped.
