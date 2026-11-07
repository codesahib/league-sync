"""Isolated Playwright backend; never resets the interactive demo database."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LEAGUE_DB"] = str(Path(__file__).resolve().parents[1] / "data" / "ui-test.sqlite3")
os.environ["SYNC_AUTORUN"] = "0"
from backend.seed import seed
import uvicorn

seed()
uvicorn.run("backend.app:app", host="127.0.0.1", port=8011)
