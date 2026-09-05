import json

import pytest
from fastapi.testclient import TestClient
from erlobiznes.web_app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_save_path(tmp_path, monkeypatch):
    """Point SAVE_PATH into tmp_path so tests never touch the real tempdir."""
    from erlobiznes import web_app

    path = tmp_path / "erlo_save.json"
    monkeypatch.setattr(web_app, "SAVE_PATH", str(path))
    return path


def _roll_to_pending(mocker):
    """Reset, then deterministically land on Ateny (idx 3)."""
    client.post("/reset")
    mocker.patch.object(app.state.game.dice, "roll", side_effect=[1, 2])
    return client.post("/roll").json()


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "ErloBiznes" in response.text


def test_get_state():
    response = client.get("/state")
    assert response.status_code == 200
    data = response.json()
    assert "players" in data
    assert "board" in data
    assert "current_player_idx" in data


def test_roll_dice(mocker):
    client.post("/reset")
    mocker.patch.object(app.state.game.dice, "roll", side_effect=[1, 3])

    idx1 = 0

    response = client.post("/roll")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert data["rolled_by"] == idx1
    assert data["state"]["current_player_idx"] == (idx1 + 1) % 2

    moves = data["moves"]
    assert isinstance(moves, list) and len(moves) > 0
    for move in moves:
        roll = move["roll"]
        assert 2 <= roll["total"] <= 12
        pair = roll["rolls"][0]
        assert len(pair) == 2
        for d in pair:
            assert 1 <= d <= 6
        assert roll["total"] == sum(pair)
        assert move["end"] == (move["start"] + roll["total"]) % 40
    for prev, nxt in zip(moves, moves[1:]):
        assert nxt["start"] == prev["end"]


def test_roll_blocked_while_purchase_pending(mocker):
    data = _roll_to_pending(mocker)
    assert data["state"]["pending_purchase"] is not None
    idx = data["state"]["current_player_idx"]

    state_resp = client.get("/state")
    assert state_resp.json()["pending_purchase"] is not None

    response = client.post("/roll")
    data = response.json()
    assert any("musi najpierw zdecydować" in m for m in data["messages"])
    assert data["moves"] == []
    assert data["state"]["pending_purchase"] is not None
    assert data["state"]["current_player_idx"] == idx


def test_purchase_decide_buy_advances_turn(mocker):
    _roll_to_pending(mocker)

    response = client.post("/purchase/decide", json={"decision": "buy"})
    assert response.status_code == 200
    data = response.json()
    assert any("kupił" in m for m in data["messages"])

    state = data["state"]
    assert state["pending_purchase"] is None
    prop_names = [p["name"] for p in state["players"][0]["properties"]]
    assert "Ateny" in prop_names
    assert state["players"][0]["money"] == 3000 - 120
    assert state["current_player_idx"] == 1


def test_purchase_decide_decline_leaves_unowned(mocker):
    _roll_to_pending(mocker)

    response = client.post("/purchase/decide", json={"decision": "decline"})
    assert response.status_code == 200
    data = response.json()
    assert any("nie kupił" in m for m in data["messages"])

    state = data["state"]
    assert state["pending_purchase"] is None
    assert state["players"][0]["properties"] == []
    assert state["current_player_idx"] == 1


def test_purchase_decide_invalid_body_rejected():
    response = client.post("/purchase/decide", json={"decision": "foo"})
    assert response.status_code == 422


def test_roll_after_game_over_shape():
    app.state.game.game_over = True
    response = client.post("/roll")
    data = response.json()
    assert data["state"]["game_over"] is True
    assert data["moves"] == []
    app.state.game.game_over = False


def test_reset_game():
    client.post("/roll")
    response = client.post("/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Game reset"

    state_resp = client.get("/state")
    state = state_resp.json()
    assert state["current_player_idx"] == 0
    for p in state["players"]:
        assert p["position"] == 0
        assert p["money"] == 3000


class TestPersistenceWeb:
    def test_roll_writes_save_file(self, mocker, isolated_save_path):
        client.post("/reset")
        mocker.patch.object(app.state.game.dice, "roll", side_effect=[1, 3])
        resp = client.post("/roll")
        assert resp.status_code == 200

        assert isolated_save_path.exists()
        data = json.loads(isolated_save_path.read_text())
        assert "players" in data
        assert data["version"] == 1

    def test_reset_deletes_save_file(self, isolated_save_path):
        isolated_save_path.write_text("{}")
        resp = client.post("/reset")
        assert resp.status_code == 200
        assert not isolated_save_path.exists()

    def test_debug_state_disabled_without_env(self, monkeypatch):
        monkeypatch.delenv("ERLO_ALLOW_INJECTION", raising=False)
        resp = client.post("/debug/state", json={"state": {}})
        assert resp.status_code == 403

    def test_debug_state_injects_full_state(self, monkeypatch):
        monkeypatch.delenv("ERLO_ALLOW_INJECTION", raising=False)
        monkeypatch.setenv("ERLO_ALLOW_INJECTION", "1")

        client.post("/reset")
        payload_state = app.state.game.save()
        payload_state["players"][0]["money"] = 777
        payload_state["players"][0]["position"] = 13
        payload_state["current_player_idx"] = 0

        resp = client.post("/debug/state", json={"state": payload_state})
        assert resp.status_code == 200
        assert resp.json()["message"] == "state injected"

        after = client.get("/state").json()
        assert after["players"][0]["money"] == 777
        assert after["players"][0]["position"] == 13
        assert after["current_player_idx"] == 0

        client.post("/reset")

    def test_game_over_state_reports_winner(self, monkeypatch):
        monkeypatch.delenv("ERLO_ALLOW_INJECTION", raising=False)
        monkeypatch.setenv("ERLO_ALLOW_INJECTION", "1")

        client.post("/reset")
        payload_state = app.state.game.save()
        payload_state["game_over"] = True
        payload_state["players"][0]["money"] = -100
        payload_state["current_player_idx"] = 0

        resp = client.post("/debug/state", json={"state": payload_state})
        assert resp.status_code == 200

        after = client.get("/state").json()
        assert after["game_over"] is True
        assert after["winner"] == after["players"][1]["name"]

        client.post("/reset")


class TestAuctionWeb:
    def test_roll_blocked_during_auction(self, mocker):
        client.post("/reset")
        app.state.game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
            "original_player": 0,
        }

        response = client.post("/roll")
        data = response.json()
        assert any("Trwa licytacja" in m for m in data["messages"])
        assert data["moves"] == []
        assert data["state"]["active_auction"] is not None

        app.state.game.active_auction = None

    def test_auction_bid_endpoint_advances_turn_on_close(self, mocker):
        client.post("/reset")
        app.state.game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
            "original_player": 0,
        }
        app.state.game.current_player_idx = 0

        response = client.post("/auction/bid", json={"player_idx": 0, "amount": 100})
        assert response.status_code == 200
        data = response.json()
        assert any("licytuje" in m for m in data["messages"])
        assert data["state"]["active_auction"]["current_bid"] == 100
        assert data["state"]["active_auction"]["auction_turn"] == 1

        response = client.post("/auction/pass", json={"player_idx": 1})
        assert response.status_code == 200
        data = response.json()
        assert any("wygrywa licytację" in m for m in data["messages"])
        assert data["state"]["active_auction"] is None
        assert data["state"]["current_player_idx"] == 1

        client.post("/reset")

    def test_auction_pass_endpoint_advances_turn_on_close(self, mocker):
        client.post("/reset")
        app.state.game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
            "original_player": 0,
        }
        app.state.game.current_player_idx = 0

        response = client.post("/auction/pass", json={"player_idx": 0})
        assert response.status_code == 200
        data = response.json()
        assert any("Pole pozostaje własnością banku" in m for m in data["messages"])
        assert data["state"]["active_auction"] is None
        assert data["state"]["current_player_idx"] == 1

        client.post("/reset")

    def test_auction_bid_rejected_wrong_turn(self):
        client.post("/reset")
        app.state.game.active_auction = {
            "field": 3,
            "starting_price": 60,
            "current_bid": 0,
            "current_bidder": None,
            "auction_turn": 0,
            "pass_count": 0,
            "original_player": 0,
        }

        response = client.post("/auction/bid", json={"player_idx": 1, "amount": 100})
        assert response.status_code == 200
        data = response.json()
        assert any("Nie twoja kolej" in m for m in data["messages"])

        app.state.game.active_auction = None

    def test_decline_starts_auction(self, mocker):
        client.post("/reset")
        mocker.patch.object(app.state.game.dice, "roll", side_effect=[1, 2])
        response = client.post("/roll")
        data = response.json()
        assert data["state"]["pending_purchase"] is not None

        response = client.post("/purchase/decide", json={"decision": "decline"})
        data = response.json()
        assert any("Licytacja" in m for m in data["messages"])
        assert data["state"]["active_auction"] is not None
        assert data["state"]["active_auction"]["starting_price"] == 60
        assert data["state"]["current_player_idx"] == 1

        client.post("/reset")

    def test_full_auction_flow_roll_decline_bid_pass(self, mocker):
        client.post("/reset")
        g = app.state.game
        mocker.patch.object(g.dice, "roll", side_effect=[1, 2, 3, 4])

        resp = client.post("/roll").json()
        assert resp["state"]["pending_purchase"] is not None
        assert resp["state"]["current_player_idx"] == 0

        resp = client.post("/purchase/decide", json={"decision": "decline"}).json()
        assert resp["state"]["active_auction"] is not None
        assert resp["state"]["active_auction"]["original_player"] == 0
        assert resp["state"]["current_player_idx"] == 1

        resp = client.post("/auction/bid", json={"player_idx": 1, "amount": 100}).json()
        assert resp["state"]["active_auction"]["auction_turn"] == 0
        assert resp["state"]["current_player_idx"] == 0

        resp = client.post("/auction/pass", json={"player_idx": 0}).json()
        assert resp["state"]["active_auction"] is None
        assert resp["state"]["current_player_idx"] == 1

        resp = client.post("/roll").json()
        assert resp["state"]["current_player_idx"] == 0

        client.post("/reset")

    def test_full_auction_flow_no_bids(self, mocker):
        client.post("/reset")
        g = app.state.game
        mocker.patch.object(g.dice, "roll", side_effect=[1, 2, 3, 4])

        client.post("/roll")
        resp = client.post("/purchase/decide", json={"decision": "decline"}).json()
        assert resp["state"]["current_player_idx"] == 1
        assert resp["state"]["active_auction"]["original_player"] == 0

        resp = client.post("/auction/pass", json={"player_idx": 1}).json()
        assert resp["state"]["active_auction"] is None
        assert resp["state"]["current_player_idx"] == 1

        resp = client.post("/roll").json()
        assert resp["state"]["current_player_idx"] == 0

        client.post("/reset")
