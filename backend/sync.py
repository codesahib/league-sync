"""Durable local outbox. No runtime AI; SQLite serializes competing processors.

The simulated League adapter and delivery acknowledgement commit together.
An actual remote adapter must expose equivalent idempotency at its boundary.
"""
import json
import logging
import time
from fastapi import HTTPException
from .db import rows, transaction
from .service import reconcile, require

MAX_AUTOMATIC_ATTEMPTS = 3


def audit(conn, event_id, action, detail):
    conn.execute("INSERT INTO sync_audit(event_id,action,detail) VALUES (?,?,?)",
                 (event_id, action, detail))


def workflow(conn):
    return conn.execute("SELECT workflow FROM sync_settings WHERE id=1").fetchone()[0]


def enqueue(conn, source_id):
    """Call within the same transaction as the Club change."""
    if workflow(conn) != "reliable":
        return None
    player = require(conn, "club_players", source_id)
    key = f"club:player:{source_id}:v:{player['version']}"
    cursor = conn.execute("""INSERT INTO sync_events(event_key,source_id,version,payload)
                           VALUES (?,?,?,?) ON CONFLICT(event_key) DO NOTHING""",
                          (key, source_id, player["version"], json.dumps(player, sort_keys=True)))
    event = dict(conn.execute("SELECT * FROM sync_events WHERE event_key=?", (key,)).fetchone())
    if cursor.rowcount:
        audit(conn, event["id"], "enqueued", f"Club {source_id}, version {player['version']}")
    return event


def set_workflow(conn, mode):
    old = workflow(conn)
    if old == mode:
        return {"workflow": old}
    if conn.execute("SELECT 1 FROM sync_events WHERE status!='delivered' LIMIT 1").fetchone():
        raise HTTPException(409, "Resolve or deliver outstanding jobs before changing workflow")
    if mode == "reliable":
        if reconcile(conn)["mismatch_count"]:
            raise HTTPException(409, "Activation requires aligned rosters. Reset the demo between comparisons using scripts/reset-demo.sh")
        # Reviewed cutover: only an already aligned copy can be adopted.
        conn.execute("DELETE FROM identity_map")
        conn.execute("DELETE FROM team_map")
        conn.execute("""INSERT INTO team_map(source_id,target_id)
                        SELECT c.id,l.id FROM club_teams c JOIN league_teams l ON c.code=l.code""")
        if conn.execute("SELECT COUNT(*) FROM team_map").fetchone()[0] != conn.execute("SELECT COUNT(*) FROM club_teams").fetchone()[0]:
            raise HTTPException(409, "Every Club team needs a matching League code before activation")
        conn.execute("""INSERT INTO identity_map(source_id,target_id,last_version,expected_revision)
                        SELECT c.id,l.id,c.version,l.revision FROM club_players c
                        JOIN league_players l ON l.source_ref=CAST(c.id AS TEXT)""")
    conn.execute("UPDATE sync_settings SET workflow=? WHERE id=1", (mode,))
    audit(conn, None, "workflow_changed", f"{old} -> {mode}; aligned-copy adoption on activation")
    return {"workflow": mode}


class DeliveryConflict(Exception):
    pass


def deliver(conn, event):
    player = json.loads(event["payload"])
    mapping = conn.execute("SELECT * FROM identity_map WHERE source_id=?", (event["source_id"],)).fetchone()
    if mapping and event["version"] <= mapping["last_version"]:
        return "duplicate_or_old_version_ignored"
    team = conn.execute("SELECT target_id FROM team_map WHERE source_id=?", (player["team_id"],)).fetchone()
    if not team:
        raise DeliveryConflict("Missing team mapping. Map this Club team to an explicit League team, then retry.")
    if mapping:
        target = require(conn, "league_players", mapping["target_id"])
        if target["revision"] != mapping["expected_revision"]:
            raise DeliveryConflict(f"League record {target['id']} changed in a Club-owned field. Review and explicitly approve Club authority.")
        conn.execute("""UPDATE league_players SET name=?,team_id=?,membership=?,revision=revision+1 WHERE id=?""",
                     (player["name"], team["target_id"], player["membership"], target["id"]))
        conn.execute("UPDATE identity_map SET last_version=?,expected_revision=? WHERE source_id=?",
                     (event["version"], target["revision"] + 1, event["source_id"]))
    else:
        if conn.execute("SELECT 1 FROM league_players WHERE source_ref=?", (str(event["source_id"]),)).fetchone():
            raise DeliveryConflict("Unmapped existing League identity. Investigate instead of guessing a match.")
        cursor = conn.execute("INSERT INTO league_players(source_ref,team_id,name,membership) VALUES (?,?,?,?)",
                              (str(event["source_id"]), team["target_id"], player["name"], player["membership"]))
        conn.execute("INSERT INTO identity_map VALUES (?,?,?,1)", (event["source_id"], cursor.lastrowid, event["version"]))
    return "applied"


def drain(limit=50):
    summary = {"attempted": 0, "delivered": 0, "failed": 0, "conflicts": 0}
    for _ in range(limit):
        with transaction() as conn:
            if workflow(conn) != "reliable":
                break
            # A delayed, exhausted or conflicting predecessor blocks only its player.
            # Keep version checks in deliver(): replayed, already-applied events remain no-ops.
            event = conn.execute("""SELECT e.* FROM sync_events e WHERE
                (e.status='pending' OR (e.status='failed' AND e.attempts<?))
                AND e.next_attempt<=?
                AND NOT EXISTS (
                    SELECT 1 FROM sync_events earlier
                    WHERE earlier.source_id=e.source_id AND earlier.version<e.version
                    AND earlier.status!='delivered'
                ) ORDER BY e.id LIMIT 1""", (MAX_AUTOMATIC_ATTEMPTS, time.time())).fetchone()
            if event is None:
                break
            event = dict(event)
            attempt = event["attempts"] + 1
            summary["attempted"] += 1
            budget = conn.execute("SELECT failure_budget FROM sync_settings WHERE id=1").fetchone()[0]
            if budget:
                conn.execute("UPDATE sync_settings SET failure_budget=failure_budget-1 WHERE id=1")
            # Roll back all adapter effects on any ordinary exception, while retaining
            # consumed fault simulation and durable failure metadata in the outer transaction.
            conn.execute("SAVEPOINT delivery")
            try:
                if budget:
                    raise ConnectionError("Simulated League network outage; target was not changed")
                outcome = deliver(conn, event)
            except Exception as exc:
                conn.execute("ROLLBACK TO delivery")
                conn.execute("RELEASE delivery")
                status = "conflict" if isinstance(exc, DeliveryConflict) else "failed"
                known = isinstance(exc, (ConnectionError, DeliveryConflict))
                error = str(exc) if known else f"{type(exc).__name__}: {exc}"
                if not known:
                    logging.exception("Unexpected adapter failure for event %s", event["event_key"])
                next_attempt = (time.time() + 2 ** attempt
                                if status == "failed" and attempt < MAX_AUTOMATIC_ATTEMPTS else 0)
                conn.execute("""UPDATE sync_events SET status=?,attempts=?,next_attempt=?,last_error=?,
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
                             (status, attempt, next_attempt, error, event["id"]))
                audit(conn, event["id"], status, f"Attempt {attempt}: {error}")
                summary["failed" if status == "failed" else "conflicts"] += 1
            else:
                conn.execute("RELEASE delivery")
                conn.execute("""UPDATE sync_events SET status='delivered',attempts=?,last_error=NULL,
                    next_attempt=0,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""", (attempt, event["id"]))
                audit(conn, event["id"], outcome, f"Attempt {attempt}; {event['event_key']}")
                summary["delivered"] += 1
    return summary


def retry(conn, event_id):
    event = require(conn, "sync_events", event_id)
    if event["status"] != "failed":
        raise HTTPException(409, "Retry is available only for failed deliveries; conflicts need resolution")
    conn.execute("UPDATE sync_events SET status='pending',next_attempt=0 WHERE id=?", (event_id,))
    audit(conn, event_id, "retry_requested", "Operator requested another attempt; history retained")
    return {"status": "pending"}


def replay(conn, event_id):
    event = require(conn, "sync_events", event_id)
    if event["status"] != "delivered":
        raise HTTPException(409, "Only delivered events can be replayed; use retry or resolve otherwise")
    conn.execute("UPDATE sync_events SET status='pending',next_attempt=0 WHERE id=?", (event_id,))
    audit(conn, event_id, "replay_requested", "Same immutable event key; duplicate delivery simulation")
    return {"status": "pending", "event_key": event["event_key"]}


def resolve(conn, event_id, expected_revision, reason):
    event = require(conn, "sync_events", event_id)
    if event["status"] != "conflict":
        raise HTTPException(409, "Only a conflicting event can be resolved")
    mapping = conn.execute("SELECT * FROM identity_map WHERE source_id=?", (event["source_id"],)).fetchone()
    if not mapping:
        raise HTTPException(409, "Identity is unmapped. Resolve the mapping before approving authority")
    target = require(conn, "league_players", mapping["target_id"])
    if target["revision"] != expected_revision:
        raise HTTPException(409, "League record changed since review. Refresh and review again")
    conn.execute("UPDATE identity_map SET expected_revision=? WHERE source_id=?", (target["revision"], event["source_id"]))
    conn.execute("UPDATE sync_events SET status='pending',next_attempt=0 WHERE id=?", (event_id,))
    audit(conn, event_id, "authority_approved", f"Operator approved Club fields over League revision {expected_revision}. Reason: {reason}")
    return {"status": "pending"}


def snapshot(conn):
    counts = {status: 0 for status in ("pending", "delivered", "failed", "conflict")}
    for row in conn.execute("SELECT status,COUNT(*) AS n FROM sync_events GROUP BY status"):
        counts[row["status"]] = row["n"]
    return {"workflow": workflow(conn), "failure_budget": conn.execute("SELECT failure_budget FROM sync_settings WHERE id=1").fetchone()[0],
            "counts": counts, "events": rows(conn, "SELECT * FROM sync_events ORDER BY id DESC LIMIT 100"),
            "audit": rows(conn, "SELECT * FROM sync_audit ORDER BY id DESC LIMIT 200"),
            "identity_map": rows(conn, "SELECT * FROM identity_map ORDER BY source_id"),
            "team_map": rows(conn, "SELECT * FROM team_map ORDER BY source_id"),
            "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS}
