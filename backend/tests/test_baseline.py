def test_seed_separate_records(client):
    state = client.get("/api/state").json()
    assert len(state["clubs"]) == 2
    assert len(state["club_teams"]) == len(state["league_teams"]) == 4
    assert len(state["club_players"]) == len(state["league_players"]) == 20
    assert state["club_players"][0]["id"] != state["league_players"][0]["id"]
    assert state["reconciliation"]["mismatch_count"] == 0


def test_csv_registration_and_repeat_import(client):
    assert client.post("/api/club/players", json={"name": "Synthetic New", "team_id": 1}).status_code == 201
    content = client.get("/api/baseline/export").text
    for _ in range(2):
        assert client.post("/api/baseline/import", json={"csv": content}).json()["imported_rows"] == 21
    assert client.get("/api/state").json()["reconciliation"]["mismatch_count"] == 0


def test_transfer_is_stale_until_manual_import_known_limitation(client):
    assert client.post("/api/club/players/1/transfer", json={"team_id": 2}).status_code == 200
    state = client.get("/api/state").json()
    assert state["club_players"][0]["team_id"] == 2
    assert state["league_players"][0]["team_id"] == 101
    assert state["reconciliation"]["mismatch_count"] == 1
    csv = client.get("/api/baseline/export").text
    client.post("/api/baseline/import", json={"csv": csv})
    state = client.get("/api/state").json()
    assert len(state["league_players"]) == 21
    assert state["reconciliation"]["issues"][0]["reasons"] == ["duplicate", "stale_fields"]


def test_invalid_import_is_atomic(client):
    data = "source_ref,team_code,name,membership\n99,CN,Synthetic New,active\n100,NOPE,Synthetic Invalid,active\n"
    assert client.post("/api/baseline/import", json={"csv": data}).status_code == 422
    assert len(client.get("/api/state").json()["league_players"]) == 20


def test_validation_and_missing_records(client):
    assert client.post("/api/club/players/1/transfer", json={"team_id": 3}).status_code == 422
    assert client.post("/api/club/players/999/transfer", json={"team_id": 2}).status_code == 404
    assert client.post("/api/club/players", json={"name": "  ", "team_id": 1}).status_code == 422
