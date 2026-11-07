"""Original CSV workflow: a team-scoped registration importer."""
import csv
import io
from fastapi import HTTPException
from .db import rows


def require(conn, table, item_id):
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{table} record {item_id} does not exist")
    return dict(row)


def export_csv(conn):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["source_ref", "team_code", "name", "membership"])
    for row in conn.execute("SELECT p.*,t.code FROM club_players p JOIN club_teams t ON t.id=p.team_id ORDER BY p.id"):
        writer.writerow([row["id"], row["code"], row["name"], row["membership"]])
    return output.getvalue()


def import_csv(conn, content):
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames != ["source_ref", "team_code", "name", "membership"]:
        raise HTTPException(422, "CSV headers must be source_ref,team_code,name,membership")
    count = 0
    try:
        for row in reader:
            if count >= 1000:
                raise HTTPException(422, "CSV limit is 1000 rows")
            ref, code, name, membership = (row.get(k) for k in reader.fieldnames)
            if (None in row or not ref or not ref.isascii() or not ref.isdecimal()
                    or len(ref) > 10 or int(ref) < 1 or str(int(ref)) != ref
                    or not name or not name.strip() or len(name) > 80
                    or membership not in ("active", "inactive")):
                raise HTTPException(422, f"Invalid CSV row {count + 2}")
            team = conn.execute("SELECT id FROM league_teams WHERE code=?", (code,)).fetchone()
            if not team:
                raise HTTPException(422, f"Unknown League team code on row {count + 2}: {code}")
            conn.execute("""INSERT INTO league_players(source_ref,team_id,name,membership) VALUES (?,?,?,?)
                ON CONFLICT(source_ref,team_id) DO UPDATE SET name=excluded.name,
                membership=excluded.membership,revision=league_players.revision+1""",
                         (ref, team["id"], name.strip(), membership))
            count += 1
    except (csv.Error, TypeError, ValueError) as exc:
        raise HTTPException(422, "Malformed CSV") from exc
    return {"imported_rows": count}


def reconcile(conn):
    issues = []
    club = rows(conn, "SELECT p.*,t.code FROM club_players p JOIN club_teams t ON p.team_id=t.id ORDER BY p.id")
    league = rows(conn, "SELECT p.*,t.code FROM league_players p JOIN league_teams t ON p.team_id=t.id ORDER BY p.id")
    source_refs = {str(p["id"]) for p in club}
    reliable = conn.execute("SELECT workflow FROM sync_settings WHERE id=1").fetchone()[0] == "reliable"
    team_map = {r["source_id"]: r["target_id"] for r in conn.execute("SELECT * FROM team_map")} if reliable else {}
    for p in club:
        matches = [r for r in league if r["source_ref"] == str(p["id"])]
        reasons = []
        if not matches:
            reasons.append("missing")
        if len(matches) > 1:
            reasons.append("duplicate")
        if any((r["team_id"] != team_map.get(p["team_id"]) if reliable else r["code"] != p["code"])
               or r["name"] != p["name"] or r["membership"] != p["membership"] for r in matches):
            reasons.append("stale_fields")
        if reasons:
            issues.append({"source_id": p["id"], "name": p["name"], "reasons": reasons,
                           "league_ids": [r["id"] for r in matches]})
    for r in league:
        if r["source_ref"] not in source_refs:
            issues.append({"source_id": r["source_ref"], "name": r["name"], "reasons": ["orphan"], "league_ids": [r["id"]]})
    return {"mismatch_count": len(issues), "issues": issues,
            "club_count": len(club), "league_count": len(league)}


def state(conn):
    return {
        "clubs": rows(conn, "SELECT * FROM clubs ORDER BY id"),
        "club_teams": rows(conn, "SELECT * FROM club_teams ORDER BY id"),
        "league_teams": rows(conn, "SELECT * FROM league_teams ORDER BY id"),
        "club_players": rows(conn, "SELECT * FROM club_players ORDER BY id"),
        "league_players": rows(conn, "SELECT * FROM league_players ORDER BY id"),
        "reconciliation": reconcile(conn),
    }
