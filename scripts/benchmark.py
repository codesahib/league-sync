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
            if mode == "reliable":
                checked(c.post("/api/workflow", json={"workflow": "reliable"}))
            for player_id in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]:
                checked(c.post(f"/api/club/players/{player_id}/transfer", json={"team_id": 2 if player_id < 10 else 4}))
            before = checked(c.get("/api/state"))["reconciliation"]
            duplicate_ignored = 0
            operator_actions = []
            if mode == "baseline":
                csv = c.get("/api/baseline/export").text
                operator_actions.append("export CSV")
                accepted = checked(c.post("/api/baseline/import", json={"csv": csv}))["imported_rows"]
                operator_actions.append("upload CSV")
                checked(c.get("/api/state"))
                operator_actions.append("inspect reconciliation")
                # Duplicate replay is an experimental intervention, not routine operator work.
                accepted += checked(c.post("/api/baseline/import", json={"csv": csv}))["imported_rows"]
            else:
                accepted = checked(c.post("/api/sync/process"))["delivered"]
                events = checked(c.get("/api/state"))["sync"]["events"]
                for event in events:
                    checked(c.post(f"/api/sync/events/{event['id']}/replay"))
                accepted += checked(c.post("/api/sync/process"))["delivered"]
                duplicate_ignored = sum(a["action"] == "duplicate_or_old_version_ignored" for a in checked(c.get("/api/state"))["sync"]["audit"])
            final = checked(c.get("/api/state"))
            return {"mode": mode, "seed_players": 20, "transfers": 10,
                    "mismatches_before_delivery": before["mismatch_count"],
                    "mismatches_after_replay": final["reconciliation"]["mismatch_count"],
                    "league_records_after_replay": len(final["league_players"]),
                    "transport_accepted_records": accepted,
                    "correctly_reconciled_transfers": 10 - final["reconciliation"]["mismatch_count"],
                    "manual_handoff_actions_per_transfer": len(operator_actions),
                    "operator_action_trace": operator_actions,
                    "duplicate_events_ignored": duplicate_ignored,
                    "physical_delivery_unit": "CSV row" if mode == "baseline" else "versioned event",
                    "note": "Source transfer and one-time activation excluded. Process endpoint replaces worker ticks in the harness. Acceptance counts have different payload units; no human timing measured."}


def failure_probe(mode):
    """One transfer, one injected outage, retry, then duplicate delivery in both modes."""
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as folder:
        os.environ["LEAGUE_DB"] = str(Path(folder) / "failure.sqlite3")
        seed()
        with TestClient(app) as c:
            if mode == "reliable":
                checked(c.post("/api/workflow", json={"workflow": "reliable"}))
            checked(c.post("/api/club/players/1/transfer", json={"team_id": 2}))
            attempted, successes, failures = 0, 0, 0
            if mode == "baseline":
                csv = c.get("/api/baseline/export").text
                budget = 1
                for _ in range(3):
                    attempted += 1
                    try:
                        if budget:
                            budget -= 1
                            raise ConnectionError("Injected transport outage before CSV request")
                        checked(c.post("/api/baseline/import", json={"csv": csv}))
                        successes += 1
                    except ConnectionError:
                        failures += 1
                        assert checked(c.get("/api/state"))["league_players"][0]["team_id"] == 101
            else:
                checked(c.post("/api/sync/failure", json={"attempts": 1}))
                results = [checked(c.post("/api/sync/process"))]
                assert checked(c.get("/api/state"))["league_players"][0]["team_id"] == 101
                checked(c.post("/api/sync/events/1/retry"))
                results.append(checked(c.post("/api/sync/process")))
                checked(c.post("/api/sync/events/1/replay"))
                results.append(checked(c.post("/api/sync/process")))
                attempted = sum(r["attempted"] for r in results)
                successes = sum(r["delivered"] for r in results)
                failures = sum(r["failed"] for r in results)
            final = checked(c.get("/api/state"))
            return {"delivery_attempts": attempted, "accepted_deliveries": successes,
                    "injected_failures": failures, "final_mismatches": final["reconciliation"]["mismatch_count"],
                    "league_records": len(final["league_players"]),
                    "durable_failure_audit_entries": sum(a["action"] == "failed" for a in final["sync"]["audit"]),
                    "delivery_payload": "20-row CSV snapshot" if mode == "baseline" else "one immutable event"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "reliable", "both"], default="both")
    parser.add_argument("--output", default="evidence/comparison.json")
    args = parser.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    modes = ["baseline", "reliable"] if args.mode == "both" else [args.mode]
    result = {"method": "Fresh identical 20-player seeds; 10 fixed transfers; one full duplicate replay. Separate identical outage/retry/replay probe. No timings.",
              "batch": {mode: experiment(mode) for mode in modes},
              "failure_probe": {mode: failure_probe(mode) for mode in modes}}
    if "reliable" in modes:
        assert result["batch"]["reliable"]["mismatches_after_replay"] == 0
        assert result["batch"]["reliable"]["league_records_after_replay"] == 20
        assert result["batch"]["reliable"]["duplicate_events_ignored"] == 10
        assert result["failure_probe"]["reliable"]["final_mismatches"] == 0
    for mode in modes:
        assert result["failure_probe"][mode]["delivery_attempts"] == 3
        assert result["failure_probe"][mode]["accepted_deliveries"] == 2
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
