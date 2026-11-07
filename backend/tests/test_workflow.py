"""Workflow and replay state-machine regressions."""
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from backend import sync
from backend.db import transaction


def state(client):
    response = client.get("/api/state")
    response.raise_for_status()
    return response.json()


@pytest.fixture
def delivered_event(client):
    assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 200
    assert client.post("/api/club/players/1/transfer", json={"team_id": 2}).status_code == 200
    assert client.post("/api/sync/process").json()["delivered"] == 1
    return state(client)["sync"]["events"][0]["id"]


def test_reported_replay_in_baseline_sequence_cannot_deadlock(client, delivered_event):
    assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 200
    before = state(client)
    replay = client.post(f"/api/sync/events/{delivered_event}/replay")
    after_replay = state(client)
    processing = client.post("/api/sync/process")
    reactivation = client.post("/api/workflow", json={"workflow": "reliable"})

    assert replay.status_code == 409, (
        f"Replay returned {replay.status_code}; processing={processing.json()}; "
        f"reactivation={reactivation.status_code} {reactivation.json()}"
    )
    assert "Reliable sync" in replay.json()["detail"]
    assert after_replay == before
    assert processing.json()["attempted"] == 0
    assert reactivation.status_code == 200
    current = state(client)
    assert current["sync"]["workflow"] == "reliable"
    assert current["sync"]["events"][0]["status"] == "delivered"
    assert current["league_players"] == before["league_players"]


def trap_legacy_replay(client, event_id):
    """Model the old endpoint's committed writes; the fixed API must reject them."""
    assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 200
    with transaction() as conn:
        conn.execute("UPDATE sync_events SET status='pending',next_attempt=0 WHERE id=?", (event_id,))
        sync.audit(conn, event_id, "replay_requested", "Legacy CSV-mode replay from before the guard")


def test_valid_transitions_and_idempotent_selection(client):
    before = state(client)
    assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 200
    assert state(client) == before
    for mode in ["reliable", "baseline", "reliable"]:
        assert client.post("/api/workflow", json={"workflow": mode}).status_code == 200
        selected = state(client)
        assert selected["sync"]["workflow"] == mode
        assert selected["reconciliation"]["mismatch_count"] == 0
        assert client.post("/api/workflow", json={"workflow": mode}).status_code == 200
        assert state(client) == selected
    assert state(client)["league_players"] == before["league_players"]


def test_reliable_replay_blocks_switch_until_processed(client, delivered_event):
    before = state(client)
    assert client.post(f"/api/sync/events/{delivered_event}/replay").status_code == 200
    pending = state(client)
    response = client.post("/api/workflow", json={"workflow": "baseline"})
    assert response.status_code == 409 and "Stay in Reliable sync" in response.json()["detail"]
    assert state(client) == pending
    assert client.post(f"/api/sync/events/{delivered_event}/replay").status_code == 409
    assert state(client) == pending
    assert client.post("/api/sync/process").json()["delivered"] == 1
    after = state(client)
    assert after["league_players"] == before["league_players"]
    assert after["sync"]["identity_map"] == before["sync"]["identity_map"]
    assert after["sync"]["events"][0]["attempts"] == 2
    assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 200


@pytest.mark.parametrize("status", ["pending", "failed", "conflict"])
def test_unresolved_original_deliveries_cannot_be_switched_out_of_reliable(client, status):
    assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 200
    assert client.post("/api/club/players/1/transfer", json={"team_id": 2}).status_code == 200
    if status == "failed":
        client.post("/api/sync/failure", json={"attempts": 1})
        assert client.post("/api/sync/process").json()["failed"] == 1
    elif status == "conflict":
        client.patch("/api/league/players/1001/local-edit", json={"name": "Synthetic Conflict", "expected_revision": 1})
        assert client.post("/api/sync/process").json()["conflicts"] == 1
    before = state(client)
    assert before["sync"]["events"][0]["status"] == status
    response = client.post("/api/workflow", json={"workflow": "baseline"})
    assert response.status_code == 409 and "Stay in Reliable sync" in response.json()["detail"]
    assert state(client) == before


def test_legacy_trap_recovery_preserves_delivery_history_and_target(client, delivered_event):
    trap_legacy_replay(client, delivered_event)
    before = state(client)
    blocked = client.post("/api/workflow", json={"workflow": "reliable"})
    assert blocked.status_code == 409 and "/cancel-replay" in blocked.json()["detail"]
    assert state(client) == before
    reason = "Reviewed the original delivery; cancel only the duplicate replay."
    recovered = client.post(f"/api/sync/events/{delivered_event}/cancel-replay", json={"reason": reason})
    assert recovered.status_code == 200 and recovered.json()["cancelled_replay"] is True
    after = state(client)
    assert after["sync"]["workflow"] == "baseline"
    assert after["sync"]["events"][0]["status"] == "delivered"
    for field in ["attempts", "event_key", "payload", "source_id", "version", "created_at"]:
        assert after["sync"]["events"][0][field] == before["sync"]["events"][0][field]
    for field in ["league_players", "club_players", "league_teams", "club_teams"]:
        assert after[field] == before[field]
    for field in ["identity_map", "team_map"]:
        assert after["sync"][field] == before["sync"][field]
    assert after["sync"]["audit"][1:] == before["sync"]["audit"]
    assert after["sync"]["audit"][0]["action"] == "replay_cancelled"
    assert reason in after["sync"]["audit"][0]["detail"]
    # Repeating cancellation cannot create another recovery/audit or mutate the delivered event.
    assert client.post(f"/api/sync/events/{delivered_event}/cancel-replay", json={"reason": reason}).status_code == 409
    assert state(client) == after
    assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 200
    assert client.post(f"/api/sync/events/{delivered_event}/replay").status_code == 200
    assert client.post("/api/sync/process").json()["delivered"] == 1
    assert state(client)["league_players"] == before["league_players"]


@pytest.mark.parametrize("missing_proof", ["mapping", "version", "replay_history", "delivery_history"])
def test_cancellation_requires_independent_delivery_and_replay_proof(client, delivered_event, missing_proof):
    trap_legacy_replay(client, delivered_event)
    with transaction() as conn:
        if missing_proof == "mapping":
            conn.execute("DELETE FROM identity_map WHERE source_id=1")
        elif missing_proof == "version":
            conn.execute("UPDATE identity_map SET last_version=1 WHERE source_id=1")
        elif missing_proof == "replay_history":
            conn.execute("DELETE FROM sync_audit WHERE event_id=? AND action='replay_requested'", (delivered_event,))
        else:
            conn.execute("DELETE FROM sync_audit WHERE event_id=? AND action IN ('applied','duplicate_or_old_version_ignored')", (delivered_event,))
    before = state(client)
    response = client.post(f"/api/sync/events/{delivered_event}/cancel-replay", json={"reason": "Review incomplete delivery evidence"})
    assert response.status_code == 409 and "cannot skip an original delivery" in response.json()["detail"]
    assert state(client) == before


def test_recovery_cannot_discard_an_unapplied_original_event(client):
    assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 200
    assert client.post("/api/club/players/1/transfer", json={"team_id": 2}).status_code == 200
    # An inconsistent legacy mode flag must not make an original delivery cancellable.
    with transaction() as conn:
        conn.execute("UPDATE sync_settings SET workflow='baseline' WHERE id=1")
    before = state(client)
    response = client.post("/api/sync/events/1/cancel-replay", json={"reason": "Attempt to skip real work"})
    assert response.status_code == 409
    assert state(client) == before


@pytest.mark.parametrize("body", [{}, {"reason": "short"}, {"reason": "   "}, {"reason": "Reviewed replay", "extra": True}])
def test_invalid_recovery_input_does_not_write(client, delivered_event, body):
    trap_legacy_replay(client, delivered_event)
    before = state(client)
    assert client.post(f"/api/sync/events/{delivered_event}/cancel-replay", json=body).status_code == 422
    assert state(client) == before


def test_cancellation_is_rejected_in_reliable_mode_and_for_missing_events(client, delivered_event):
    assert client.post(f"/api/sync/events/{delivered_event}/replay").status_code == 200
    before = state(client)
    response = client.post(f"/api/sync/events/{delivered_event}/cancel-replay", json={"reason": "Pending replay is already processable"})
    assert response.status_code == 409 and "process the queue" in response.json()["detail"]
    assert client.post("/api/sync/events/999/cancel-replay", json={"reason": "Nonexistent event"}).status_code == 404
    assert client.post("/api/sync/events/999/replay").status_code == 404
    assert state(client) == before


def test_recovery_rolls_back_if_its_audit_cannot_be_saved(client, delivered_event, monkeypatch):
    trap_legacy_replay(client, delivered_event)
    before = state(client)
    original = sync.audit

    def failed_audit(conn, event_id, action, detail):
        if action == "replay_cancelled":
            raise RuntimeError("Cannot record recovery audit")
        return original(conn, event_id, action, detail)

    monkeypatch.setattr(sync, "audit", failed_audit)
    with pytest.raises(RuntimeError, match="recovery audit"):
        client.post(f"/api/sync/events/{delivered_event}/cancel-replay", json={"reason": "Reviewed original delivery"})
    assert state(client) == before


def test_failed_activation_rolls_back_mapping_rebuild(client, delivered_event):
    assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 200
    assert client.post("/api/club/teams", json={"club_id": 1, "name": "Synthetic Unmapped Team", "code": "UT"}).status_code == 201
    before = state(client)
    response = client.post("/api/workflow", json={"workflow": "reliable"})
    assert response.status_code == 409 and "matching League code" in response.json()["detail"]
    assert state(client) == before


def test_switch_and_replay_race_cannot_commit_a_trapped_event(client, delivered_event):
    barrier = Barrier(2)

    def request(kind):
        barrier.wait(timeout=5)
        if kind == "switch":
            return client.post("/api/workflow", json={"workflow": "baseline"})
        return client.post(f"/api/sync/events/{delivered_event}/replay")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, ["switch", "replay"]))
    assert sorted(response.status_code for response in results) == [200, 409]
    current = state(client)
    if current["sync"]["workflow"] == "baseline":
        assert current["sync"]["events"][0]["status"] == "delivered"
        assert client.post("/api/workflow", json={"workflow": "reliable"}).status_code == 200
    else:
        assert current["sync"]["events"][0]["status"] == "pending"
        assert client.post("/api/sync/process").json()["delivered"] == 1
        assert client.post("/api/workflow", json={"workflow": "baseline"}).status_code == 200
