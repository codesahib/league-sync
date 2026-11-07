import os
import sqlite3
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ConfigDict
from .db import initialize, transaction
from . import service, sync


@asynccontextmanager
async def lifespan(app):
    initialize()
    stop = asyncio.Event()
    async def worker():
        while not stop.is_set():
            try:
                await asyncio.to_thread(sync.drain)
            except Exception:
                logging.exception("Outbox worker failed; committed pending jobs remain recoverable")
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.5)
            except TimeoutError:
                pass
    task = asyncio.create_task(worker()) if os.getenv("SYNC_AUTORUN", "1") == "1" else None
    try:
        yield
    finally:
        stop.set()
        if task:
            await task


app = FastAPI(title="League Sync Reliability Lab", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Transfer(Input):
    team_id: int = Field(gt=0)


class Registration(Input):
    name: str = Field(min_length=1, max_length=80)
    team_id: int = Field(gt=0)
    membership: Literal["active", "inactive"] = "active"


class Team(Input):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,7}$")
    club_id: int | None = Field(default=None, gt=0)


class Import(Input):
    csv: str = Field(min_length=1, max_length=200000)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/state")
def state():
    with transaction() as conn:
        return {**service.state(conn), "sync": sync.snapshot(conn),
                "worker_enabled": os.getenv("SYNC_AUTORUN", "1") == "1"}


@app.post("/api/club/players", status_code=201)
def register(body: Registration):
    with transaction() as conn:
        team = service.require(conn, "club_teams", body.team_id)
        cursor = conn.execute("INSERT INTO club_players(club_id,team_id,name,membership) VALUES (?,?,?,?)",
                              (team["club_id"], body.team_id, body.name, body.membership))
        sync.enqueue(conn, cursor.lastrowid)
        return service.require(conn, "club_players", cursor.lastrowid)


@app.post("/api/club/players/{player_id}/transfer")
def transfer(player_id: int, body: Transfer):
    with transaction() as conn:
        player = service.require(conn, "club_players", player_id)
        team = service.require(conn, "club_teams", body.team_id)
        if team["club_id"] != player["club_id"]:
            raise HTTPException(422, "Transfers must stay within the player's club")
        if player["team_id"] != body.team_id:
            conn.execute("UPDATE club_players SET team_id=?,version=version+1 WHERE id=?", (body.team_id, player_id))
            sync.enqueue(conn, player_id)
        return service.require(conn, "club_players", player_id)


@app.post("/api/{portal}/teams", status_code=201)
def add_team(portal: Literal["club", "league"], body: Team):
    with transaction() as conn:
        try:
            if portal == "club":
                service.require(conn, "clubs", body.club_id)
                cur = conn.execute("INSERT INTO club_teams(club_id,name,code) VALUES (?,?,?)", (body.club_id, body.name, body.code))
            else:
                cur = conn.execute("INSERT INTO league_teams(name,code) VALUES (?,?)", (body.name, body.code))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Team code already exists in this portal") from exc
        return service.require(conn, f"{portal}_teams", cur.lastrowid)


@app.get("/api/baseline/export", response_class=PlainTextResponse)
def export():
    with transaction() as conn:
        return PlainTextResponse(service.export_csv(conn), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="club-roster.csv"'})


@app.post("/api/baseline/import")
def import_roster(body: Import):
    with transaction() as conn:
        if sync.workflow(conn) != "baseline":
            raise HTTPException(409, "CSV imports are disabled during reliable synchronization; use the outbox")
        return service.import_csv(conn, body.csv)


class Eligibility(Input):
    eligible: bool


@app.patch("/api/league/players/{player_id}/eligibility")
def eligibility(player_id: int, body: Eligibility):
    with transaction() as conn:
        service.require(conn, "league_players", player_id)
        conn.execute("UPDATE league_players SET eligible=? WHERE id=?", (body.eligible, player_id))
        return service.require(conn, "league_players", player_id)


class Workflow(Input):
    workflow: Literal["baseline", "reliable"]


class Failure(Input):
    attempts: int = Field(ge=0, le=10)


class Resolve(Input):
    expected_revision: int = Field(gt=0)
    reason: str = Field(min_length=8, max_length=240)


class Mapping(Input):
    source_id: int = Field(gt=0)
    target_id: int = Field(gt=0)


class LeagueEdit(Input):
    name: str = Field(min_length=1, max_length=80)
    expected_revision: int = Field(gt=0)


@app.post("/api/workflow")
def workflow(body: Workflow):
    with transaction() as conn:
        return sync.set_workflow(conn, body.workflow)


@app.post("/api/sync/process")
def process():
    return sync.drain()


@app.post("/api/sync/failure")
def simulate_failure(body: Failure):
    with transaction() as conn:
        conn.execute("UPDATE sync_settings SET failure_budget=? WHERE id=1", (body.attempts,))
        sync.audit(conn, None, "failure_simulated", f"Next {body.attempts} delivery attempts fail before target write")
    return {"failure_budget": body.attempts}


@app.post("/api/sync/events/{event_id}/retry")
def retry(event_id: int):
    with transaction() as conn:
        return sync.retry(conn, event_id)


@app.post("/api/sync/events/{event_id}/replay")
def replay(event_id: int):
    with transaction() as conn:
        return sync.replay(conn, event_id)


@app.post("/api/sync/events/{event_id}/resolve")
def resolve(event_id: int, body: Resolve):
    with transaction() as conn:
        return sync.resolve(conn, event_id, body.expected_revision, body.reason)


@app.post("/api/sync/team-map")
def team_map(body: Mapping):
    with transaction() as conn:
        service.require(conn, "club_teams", body.source_id)
        service.require(conn, "league_teams", body.target_id)
        if conn.execute("SELECT 1 FROM team_map WHERE source_id=?", (body.source_id,)).fetchone():
            raise HTTPException(409, "An existing team mapping cannot be silently reassigned")
        try:
            conn.execute("INSERT INTO team_map VALUES (?,?)", (body.source_id, body.target_id))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "League team is already mapped") from exc
        sync.audit(conn, None, "team_mapped", f"Club team {body.source_id} -> League team {body.target_id}")
        # A missing mapping has no target identity for the ordinary authority decision.
        for event in conn.execute("SELECT * FROM sync_events WHERE status='conflict'").fetchall():
            import json
            if json.loads(event["payload"])["team_id"] == body.source_id and event["last_error"].startswith("Missing team mapping"):
                conn.execute("UPDATE sync_events SET status='pending',next_attempt=0 WHERE id=?", (event["id"],))
                sync.audit(conn, event["id"], "mapping_resolved", "Explicit team mapping supplied; queued again")
        return {"source_id": body.source_id, "target_id": body.target_id}


@app.patch("/api/league/players/{player_id}/local-edit")
def local_edit(player_id: int, body: LeagueEdit):
    """Legacy League screen can edit name; integration must detect this conflict."""
    with transaction() as conn:
        player = service.require(conn, "league_players", player_id)
        if player["revision"] != body.expected_revision:
            raise HTTPException(409, "League record changed since it was loaded")
        conn.execute("UPDATE league_players SET name=?,revision=revision+1 WHERE id=?", (body.name, player_id))
        sync.audit(conn, None, "league_local_edit", f"League {player_id}: name edited at revision {player['revision']}")
        return service.require(conn, "league_players", player_id)
