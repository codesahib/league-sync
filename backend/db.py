"""Local storage. Club and League own independent tables and identifiers."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def connect():
    path = Path(os.environ.get("LEAGUE_DB", str(ROOT / "data" / "demo.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def transaction():
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS club_teams(
 id INTEGER PRIMARY KEY, club_id INTEGER NOT NULL REFERENCES clubs(id),
 name TEXT NOT NULL, code TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS club_players(
 id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER NOT NULL REFERENCES clubs(id),
 team_id INTEGER NOT NULL REFERENCES club_teams(id), name TEXT NOT NULL,
 membership TEXT NOT NULL CHECK(membership IN ('active','inactive')),
 version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS league_teams(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS league_players(
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_ref TEXT NOT NULL,
 team_id INTEGER NOT NULL REFERENCES league_teams(id), name TEXT NOT NULL,
 membership TEXT NOT NULL CHECK(membership IN ('active','inactive')),
 eligible INTEGER NOT NULL DEFAULT 1 CHECK(eligible IN (0,1)),
 revision INTEGER NOT NULL DEFAULT 1, UNIQUE(source_ref,team_id));
CREATE TABLE IF NOT EXISTS sync_settings(
 id INTEGER PRIMARY KEY CHECK(id=1), workflow TEXT NOT NULL CHECK(workflow IN ('baseline','reliable')),
 failure_budget INTEGER NOT NULL DEFAULT 0 CHECK(failure_budget>=0));
INSERT OR IGNORE INTO sync_settings(id,workflow) VALUES(1,'baseline');
CREATE TABLE IF NOT EXISTS team_map(
 source_id INTEGER PRIMARY KEY REFERENCES club_teams(id),
 target_id INTEGER NOT NULL UNIQUE REFERENCES league_teams(id));
CREATE TABLE IF NOT EXISTS identity_map(
 source_id INTEGER PRIMARY KEY REFERENCES club_players(id),
 target_id INTEGER NOT NULL UNIQUE REFERENCES league_players(id),
 last_version INTEGER NOT NULL, expected_revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sync_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
 source_id INTEGER NOT NULL REFERENCES club_players(id), version INTEGER NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','delivered','failed','conflict')),
 attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
 last_error TEXT, created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(source_id,version));
CREATE INDEX IF NOT EXISTS events_due ON sync_events(status,next_attempt,id);
CREATE TABLE IF NOT EXISTS sync_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER REFERENCES sync_events(id),
 action TEXT NOT NULL, detail TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
"""


def initialize():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def rows(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params)]
