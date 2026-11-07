import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ConfigDict
from .db import initialize, transaction
from . import service


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield


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
        return service.state(conn)


@app.post("/api/club/players", status_code=201)
def register(body: Registration):
    with transaction() as conn:
        team = service.require(conn, "club_teams", body.team_id)
        cursor = conn.execute("INSERT INTO club_players(club_id,team_id,name,membership) VALUES (?,?,?,?)",
                              (team["club_id"], body.team_id, body.name, body.membership))
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
        return service.import_csv(conn, body.csv)


class Eligibility(Input):
    eligible: bool


@app.patch("/api/league/players/{player_id}/eligibility")
def eligibility(player_id: int, body: Eligibility):
    with transaction() as conn:
        service.require(conn, "league_players", player_id)
        conn.execute("UPDATE league_players SET eligible=? WHERE id=?", (body.eligible, player_id))
        return service.require(conn, "league_players", player_id)
