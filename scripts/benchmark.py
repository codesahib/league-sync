"""Comparable synthetic API experiment. Never touches the interactive demo DB."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from backend.app import app
from backend.seed import seed


def checked(response):
    response.raise_for_status()
    return response.json()


def experiment(mode):
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as folder:
        os.environ["LEAGUE_DB"] = str(Path(folder) / "benchmark.sqlite3")
        os.environ["SYNC_AUTORUN"] = "0"
        seed()
        with TestClient(app) as c:
            for player_id in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]:
                checked(c.post(f"/api/club/players/{player_id}/transfer", json={"team_id": 2 if player_id < 10 else 4}))
            before = checked(c.get("/api/state"))["reconciliation"]
            csv = c.get("/api/baseline/export").text
            accepted = sum(checked(c.post("/api/baseline/import", json={"csv": csv}))["imported_rows"] for _ in range(2))
            final = checked(c.get("/api/state"))
            return {"mode": mode, "seed_players": 20, "transfers": 10,
                    "mismatches_before_delivery": before["mismatch_count"],
                    "mismatches_after_replay": final["reconciliation"]["mismatch_count"],
                    "league_records_after_replay": len(final["league_players"]),
                    "transport_accepted_records": accepted,
                    "correctly_reconciled_transfers": 10 - final["reconciliation"]["mismatch_count"],
                    "manual_handoff_actions_per_transfer": 3,
                    "operator_action_trace": ["export CSV", "upload CSV", "inspect reconciliation"],
                    "note": "Source transfer excluded. Correctness and CSV acceptance are separate metrics; no human timing measured."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline"], default="baseline")
    parser.add_argument("--output", default="evidence/baseline.json")
    args = parser.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    result = experiment(args.mode)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
