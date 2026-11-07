"""Deterministic synthetic reset. Run: python -m backend.seed"""
from .db import initialize, transaction


def seed():
    initialize()
    with transaction() as conn:
        for table in ("sync_audit", "sync_events", "identity_map", "team_map", "league_players", "club_players", "league_teams", "club_teams", "clubs"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")
        conn.execute("UPDATE sync_settings SET workflow='baseline',failure_budget=0 WHERE id=1")
        conn.executemany("INSERT INTO clubs VALUES (?,?)", [(1, "Cedar Club"), (2, "Harbor Club")])
        teams = [(1, 1, "Cedar North", "CN"), (2, 1, "Cedar South", "CS"),
                 (3, 2, "Harbor East", "HE"), (4, 2, "Harbor West", "HW")]
        conn.executemany("INSERT INTO club_teams VALUES (?,?,?,?)", teams)
        conn.executemany("INSERT INTO league_teams(id,name,code) VALUES (?,?,?)",
                         [(100 + t[0], t[2], t[3]) for t in teams])
        for n in range(1, 21):
            team_id = (n - 1) // 5 + 1
            club_id = 1 if team_id <= 2 else 2
            name = f"Synthetic Player {n:02d}"
            conn.execute("INSERT INTO club_players(id,club_id,team_id,name,membership) VALUES (?,?,?,?,'active')",
                         (n, club_id, team_id, name))
            conn.execute("INSERT INTO league_players(id,source_ref,team_id,name,membership) VALUES (?,?,?,?,'active')",
                         (1000 + n, str(n), 100 + team_id, name))


if __name__ == "__main__":
    seed()
    print("Reset: 2 clubs, 4 teams, 20 Club players, 20 separate League records.")
