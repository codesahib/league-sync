from concurrent.futures import ThreadPoolExecutor
import pytest
from backend import sync
from backend.db import transaction
import time
from types import SimpleNamespace
from fastapi.testclient import TestClient
from backend.app import app


def enable(client):
    assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 200


def state(client):
    return client.get("/api/state").json()


def transfer(client, source=1, target=2):
    assert client.post(f"/api/club/players/{source}/transfer", json={"team_id": target}).status_code == 200


def test_transfer_and_duplicate_delivery(client):
    enable(client)
    transfer(client)
    assert state(client)["sync"]["counts"]["pending"] == 1
    assert client.post("/api/sync/process").json()["delivered"] == 1
    first = state(client)
    event_id = first["sync"]["events"][0]["id"]
    assert client.post(f"/api/sync/events/{event_id}/replay").status_code == 200
    assert client.post("/api/sync/process").json()["delivered"] == 1
    after = state(client)
    assert after["reconciliation"]["mismatch_count"] == 0
    assert len(after["league_players"]) == 20
    assert first["league_players"] == after["league_players"]
    assert any(a["action"] == "duplicate_or_old_version_ignored" for a in after["sync"]["audit"])


def test_temporary_failure_and_explicit_retry(client):
    enable(client)
    transfer(client)
    client.post("/api/sync/failure", json={"attempts": 1})
    assert client.post("/api/sync/process").json()["failed"] == 1
    failed = state(client)
    event = failed["sync"]["events"][0]
    assert event["status"] == "failed" and event["attempts"] == 1
    assert failed["league_players"][0]["team_id"] == 101
    assert client.post(f"/api/sync/events/{event['id']}/retry").status_code == 200
    assert client.post("/api/sync/process").json()["delivered"] == 1
    after = state(client)
    assert after["reconciliation"]["mismatch_count"] == 0
    assert after["sync"]["events"][0]["attempts"] == 2
    assert {a["action"] for a in after["sync"]["audit"]} >= {"failed", "retry_requested", "applied"}


def test_bounded_automatic_retry(client, monkeypatch):
    enable(client)
    transfer(client)
    client.post("/api/sync/failure", json={"attempts": 5})
    clock = [100.0]
    monkeypatch.setattr(sync.time, "time", lambda: clock[0])
    for _ in range(3):
        assert sync.drain()["failed"] == 1
        clock[0] += 10
    assert sync.drain()["attempted"] == 0
    assert state(client)["sync"]["events"][0]["attempts"] == 3


def test_automatic_retry_succeeds_when_due(client, monkeypatch):
    enable(client)
    transfer(client)
    client.post("/api/sync/failure", json={"attempts": 1})
    clock = [100.0]
    monkeypatch.setattr(sync.time, "time", lambda: clock[0])
    assert sync.drain()["failed"] == 1
    assert sync.drain()["attempted"] == 0
    clock[0] += 3
    assert sync.drain()["delivered"] == 1


def test_out_of_order_replay_cannot_undo_newer_transfer(client):
    enable(client)
    transfer(client)
    client.post("/api/sync/process")
    transfer(client, target=1)
    client.post("/api/sync/process")
    assert client.post("/api/sync/events/1/replay").status_code == 200
    client.post("/api/sync/process")
    assert state(client)["league_players"][0]["team_id"] == 101
    assert state(client)["reconciliation"]["mismatch_count"] == 0


def test_newer_pending_event_waits_for_earlier_version(client):
    enable(client)
    transfer(client)
    transfer(client, target=1)
    with transaction() as conn:
        conn.execute("UPDATE sync_events SET next_attempt=9999999999 WHERE id=1")
    assert sync.drain()["attempted"] == 0
    assert all(e["attempts"] == 0 for e in state(client)["sync"]["events"])
    with transaction() as conn:
        conn.execute("UPDATE sync_events SET next_attempt=0 WHERE id=1")
    assert sync.drain(limit=1)["delivered"] == 1
    assert state(client)["league_players"][0]["team_id"] == 102
    assert sync.drain()["delivered"] == 1
    assert state(client)["reconciliation"]["mismatch_count"] == 0


def test_conflict_requires_review_and_preserves_eligibility(client):
    enable(client)
    client.patch("/api/league/players/1001/eligibility", json={"eligible": False})
    client.patch("/api/league/players/1001/local-edit", json={"name": "Synthetic League Edit", "expected_revision": 1})
    transfer(client)
    assert client.post("/api/sync/process").json()["conflicts"] == 1
    assert state(client)["league_players"][0]["name"] == "Synthetic League Edit"
    assert client.post("/api/sync/events/1/retry").status_code == 409
    assert client.post("/api/sync/events/1/resolve", json={"expected_revision": 1, "reason": "Reviewed Club authority"}).status_code == 409
    assert client.post("/api/sync/events/1/resolve", json={"expected_revision": 2, "reason": "Reviewed Club authority"}).status_code == 200
    client.post("/api/sync/process")
    after = state(client)
    assert after["reconciliation"]["mismatch_count"] == 0
    assert after["league_players"][0]["eligible"] == 0
    assert any(a["action"] == "authority_approved" for a in after["sync"]["audit"])


def test_new_registration_is_mapped_and_idempotent(client):
    enable(client)
    player = client.post("/api/club/players", json={"name": "Synthetic New", "team_id": 1}).json()
    with transaction() as conn:
        sync.enqueue(conn, player["id"])
    assert len(state(client)["sync"]["events"]) == 1
    client.post("/api/sync/process")
    client.post("/api/sync/events/1/replay")
    client.post("/api/sync/process")
    after = state(client)
    assert len(after["league_players"]) == 21
    assert len(after["sync"]["identity_map"]) == 21
    assert after["reconciliation"]["mismatch_count"] == 0


def test_noop_transfer_does_not_emit_event(client):
    enable(client)
    transfer(client, target=1)
    assert state(client)["sync"]["counts"]["pending"] == 0


def test_club_write_and_enqueue_roll_back_together(client, monkeypatch):
    enable(client)
    def broken_enqueue(*args):
        raise RuntimeError("Injected outbox write failure")
    monkeypatch.setattr(sync, "enqueue", broken_enqueue)
    with pytest.raises(RuntimeError, match="outbox write failure"):
        transfer(client)
    assert state(client)["club_players"][0]["team_id"] == 1
    assert not state(client)["sync"]["events"]


@pytest.mark.parametrize("error_type", [RuntimeError, ConnectionError])
def test_adapter_error_after_target_write_rolls_back_and_recovers(client, monkeypatch, error_type):
    enable(client)
    transfer(client)
    original = sync.deliver
    def crashed(conn, event):
        original(conn, event)
        raise error_type("Failure before acknowledgement")
    monkeypatch.setattr(sync, "deliver", crashed)
    assert sync.drain()["failed"] == 1
    assert state(client)["league_players"][0]["team_id"] == 101
    failed = state(client)
    assert failed["sync"]["events"][0]["status"] == "failed"
    assert failed["sync"]["identity_map"][0]["last_version"] == 1
    assert failed["league_players"][0]["revision"] == 1
    assert not any(a["action"] == "applied" for a in failed["sync"]["audit"])
    monkeypatch.setattr(sync, "deliver", original)
    assert client.post("/api/sync/events/1/retry").status_code == 200
    assert sync.drain()["delivered"] == 1
    assert state(client)["reconciliation"]["mismatch_count"] == 0


def test_competing_processors_do_not_duplicate(client):
    enable(client)
    for n in range(1, 6):
        transfer(client, source=n)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: sync.drain(), range(2)))
    assert sum(r["delivered"] for r in results) == 5
    assert len(state(client)["league_players"]) == 20
    assert state(client)["reconciliation"]["mismatch_count"] == 0


def test_workflow_guards(client):
    enable(client)
    assert client.post("/api/baseline/import", json={"csv": client.get("/api/baseline/export").text}).status_code == 409
    transfer(client)
    assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 409
    assert client.post("/api/sync/events/1/replay").status_code == 409


def test_cutover_rejects_misaligned_rosters(client):
    transfer(client)
    assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 409


def test_missing_team_mapping_safe_resolution(client):
    enable(client)
    club = client.post("/api/club/teams", json={"club_id": 1, "name": "Cedar New", "code": "CX"}).json()
    league = client.post("/api/league/teams", json={"name": "League New", "code": "LX"}).json()
    transfer(client, target=club["id"])
    assert client.post("/api/sync/process").json()["conflicts"] == 1
    assert client.post("/api/sync/team-map", json={"source_id": club["id"], "target_id": league["id"]}).status_code == 200
    assert client.post("/api/sync/process").json()["delivered"] == 1
    # Codes need not match after explicit mapping; reconciliation must use the mapping.
    assert state(client)["league_players"][0]["team_id"] == league["id"]
    assert state(client)["reconciliation"]["mismatch_count"] == 0


def test_invalid_mapping_and_team_inputs(client):
    enable(client)
    assert client.post("/api/sync/team-map", json={"source_id": 999, "target_id": 101}).status_code == 404
    assert client.post("/api/sync/team-map", json={"source_id": 1, "target_id": 102}).status_code == 409
    assert client.post("/api/club/teams", json={"name": "No club", "code": "XX"}).status_code == 404
    assert client.post("/api/club/teams", json={"name": "Duplicate", "code": "CN", "club_id": 1}).status_code == 409


def test_background_worker_delivers_and_retries_without_ui(client, monkeypatch):
    monkeypatch.setenv("SYNC_AUTORUN", "1")
    with TestClient(app) as live:
        enable(live)
        live.post("/api/sync/failure", json={"attempts": 1})
        transfer(live)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            current = state(live)
            if current["sync"]["counts"]["delivered"] == 1:
                break
            time.sleep(0.05)
        assert current["reconciliation"]["mismatch_count"] == 0
        assert current["sync"]["events"][0]["attempts"] == 2


def test_pending_event_survives_connection_restart(client):
    enable(client)
    transfer(client)
    with TestClient(app) as restarted:
        assert state(restarted)["sync"]["counts"]["pending"] == 1
        assert restarted.post("/api/sync/process").json()["delivered"] == 1
        assert state(restarted)["reconciliation"]["mismatch_count"] == 0


def test_unexpected_adapter_error_is_recorded_without_blocking_other_players(client, monkeypatch):
    enable(client)
    transfer(client, source=1)
    transfer(client, source=2)
    original = sync.deliver

    def failing_player(conn, event):
        if event["source_id"] == 1:
            raise RuntimeError("Synthetic adapter bug")
        return original(conn, event)

    monkeypatch.setattr(sync, "deliver", failing_player)
    response = client.post("/api/sync/process")
    assert response.status_code == 200
    assert response.json() == {"attempted": 2, "delivered": 1, "failed": 1, "conflicts": 0}
    current = state(client)
    failed = next(e for e in current["sync"]["events"] if e["source_id"] == 1)
    assert failed["status"] == "failed" and failed["attempts"] == 1
    assert failed["next_attempt"] > 0
    assert "RuntimeError: Synthetic adapter bug" in failed["last_error"]
    assert current["league_players"][0]["team_id"] == 101
    assert current["league_players"][1]["team_id"] == 102
    assert any(a["action"] == "failed" and a["event_id"] == failed["id"]
               for a in current["sync"]["audit"])


def test_unexpected_error_exhaustion_persists_and_manual_recovery_preserves_order(client, monkeypatch):
    enable(client)
    client.patch("/api/league/players/1001/eligibility", json={"eligible": False})
    transfer(client, source=1)
    transfer(client, source=1, target=1)
    transfer(client, source=2)
    original = sync.deliver
    clock = [100.0]
    monkeypatch.setattr(sync, "time", SimpleNamespace(time=lambda: clock[0]))

    def failing_first_version(conn, event):
        if event["source_id"] == 1 and event["version"] == 2:
            raise RuntimeError("Persistent adapter error")
        return original(conn, event)

    monkeypatch.setattr(sync, "deliver", failing_first_version)
    assert sync.drain() == {"attempted": 2, "delivered": 1, "failed": 1, "conflicts": 0}
    for attempt, due in [(1, 102.0), (2, 106.0)]:
        events = {e["id"]: e for e in state(client)["sync"]["events"]}
        assert events[1]["attempts"] == attempt and events[1]["next_attempt"] == due
        assert events[2]["status"] == "pending" and events[2]["attempts"] == 0
        assert sync.drain()["attempted"] == 0  # Neither retry early nor bypass the predecessor.
        clock[0] = due
        assert sync.drain()["failed"] == 1

    # New API/DB connections observe exhausted attempts, error and audit after commit.
    with TestClient(app) as restarted:
        current = state(restarted)
        events = {e["id"]: e for e in current["sync"]["events"]}
        assert events[1]["status"] == "failed" and events[1]["attempts"] == 3
        assert events[1]["last_error"] == "RuntimeError: Persistent adapter error"
        assert events[1]["next_attempt"] == 0  # No automatic attempt remains scheduled.
        assert events[2]["status"] == "pending" and events[2]["attempts"] == 0
        assert sum(a["action"] == "failed" and a["event_id"] == 1
                   for a in current["sync"]["audit"]) == 3
        clock[0] += 100
        assert sync.drain()["attempted"] == 0

        transfer(restarted, source=2, target=1)
        assert sync.drain()["delivered"] == 1  # Exhausted player 1 still cannot block player 2.
        monkeypatch.setattr(sync, "deliver", original)
        assert sync.drain()["attempted"] == 0  # Fixing the adapter does not silently reset the budget.
        assert restarted.post("/api/sync/events/1/retry").status_code == 200
        assert sync.drain(limit=1)["delivered"] == 1
        intermediate = state(restarted)
        assert intermediate["league_players"][0]["team_id"] == 102  # Version 2 is applied first.
        assert intermediate["sync"]["identity_map"][0]["last_version"] == 2
        assert sync.drain()["delivered"] == 1
        recovered = state(restarted)
        assert recovered["league_players"][0]["team_id"] == 101  # Then version 3.
        assert recovered["league_players"][0]["eligible"] == 0
        assert recovered["reconciliation"]["mismatch_count"] == 0
        events = {e["id"]: e for e in recovered["sync"]["events"]}
        assert events[1]["attempts"] == 4 and events[1]["last_error"] is None
        assert events[2]["attempts"] == 1 and events[2]["status"] == "delivered"
        assert sum(a["action"] == "failed" and a["event_id"] == 1
                   for a in recovered["sync"]["audit"]) == 3
        assert any(a["action"] == "retry_requested" and a["event_id"] == 1
                   for a in recovered["sync"]["audit"])
        before_replay = recovered["league_players"]
        assert restarted.post("/api/sync/events/1/replay").status_code == 200
        assert sync.drain()["delivered"] == 1
        assert state(restarted)["league_players"] == before_replay


def test_unexpected_error_recovers_automatically_only_when_due(client, monkeypatch):
    enable(client)
    transfer(client)
    original = sync.deliver
    clock = [100.0]
    monkeypatch.setattr(sync, "time", SimpleNamespace(time=lambda: clock[0]))

    def broken(conn, event):
        raise RuntimeError("Temporary adapter defect")

    monkeypatch.setattr(sync, "deliver", broken)
    assert sync.drain()["failed"] == 1
    monkeypatch.setattr(sync, "deliver", original)
    assert sync.drain()["attempted"] == 0
    clock[0] += 2
    assert sync.drain()["delivered"] == 1
    recovered = state(client)
    assert recovered["reconciliation"]["mismatch_count"] == 0
    assert recovered["sync"]["events"][0]["attempts"] == 2
    assert recovered["sync"]["events"][0]["last_error"] is None
    assert not any(a["action"] == "retry_requested" for a in recovered["sync"]["audit"])


def test_conflict_blocks_newer_versions_until_explicit_resolution(client):
    enable(client)
    client.patch("/api/league/players/1001/local-edit", json={"name": "Synthetic League Edit", "expected_revision": 1})
    transfer(client, source=1)
    transfer(client, source=1, target=1)
    transfer(client, source=2)
    assert sync.drain() == {"attempted": 2, "delivered": 1, "failed": 0, "conflicts": 1}
    blocked = state(client)
    assert blocked["league_players"][0]["name"] == "Synthetic League Edit"
    assert next(e for e in blocked["sync"]["events"] if e["id"] == 2)["attempts"] == 0
    assert sync.drain()["attempted"] == 0
    assert client.post("/api/sync/events/1/retry").status_code == 409
    assert client.post("/api/sync/events/1/resolve", json={"expected_revision": 1, "reason": "Reviewed Club authority"}).status_code == 409
    assert client.post("/api/sync/events/1/resolve", json={"expected_revision": 2, "reason": "Reviewed Club authority"}).status_code == 200
    assert sync.drain()["delivered"] == 2
    assert state(client)["reconciliation"]["mismatch_count"] == 0


def test_unexpected_error_after_registration_insert_does_not_duplicate_target(client, monkeypatch):
    enable(client)
    assert client.post("/api/club/players", json={"name": "Synthetic Recovery", "team_id": 1}).status_code == 201
    original = sync.deliver

    def broken_after_insert(conn, event):
        original(conn, event)
        raise RuntimeError("Failure after target insert")

    monkeypatch.setattr(sync, "deliver", broken_after_insert)
    assert sync.drain()["failed"] == 1
    failed = state(client)
    assert len(failed["league_players"]) == len(failed["sync"]["identity_map"]) == 20
    assert failed["sync"]["events"][0]["status"] == "failed"
    monkeypatch.setattr(sync, "deliver", original)
    assert client.post("/api/sync/events/1/retry").status_code == 200
    assert sync.drain()["delivered"] == 1
    recovered = state(client)
    assert len(recovered["league_players"]) == len(recovered["sync"]["identity_map"]) == 21
    assert recovered["reconciliation"]["mismatch_count"] == 0
    assert client.post("/api/sync/events/1/replay").status_code == 200
    assert sync.drain()["delivered"] == 1
    assert state(client)["league_players"] == recovered["league_players"]
