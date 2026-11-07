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
"""


def initialize():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def rows(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params)]
