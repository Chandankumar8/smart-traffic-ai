import sys
import types

import pytest

sys.modules.setdefault("ultralytics", types.ModuleType("ultralytics"))
import config


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LANES_FILE", str(tmp_path / "lanes.json"))
    import app as app_module
    app_module.apply_lanes(app_module.load_lanes())      # fresh state, workers not started
    return app_module.app.test_client()


def test_stats_has_lane_metrics_and_comparison(client):
    d = client.get("/api/stats").get_json()
    assert len(d["lanes"]) == 4
    assert {"avg_wait", "throughput", "count", "state"} <= d["lanes"][0].keys()
    assert "comparison" in d


def test_emergency_flow(client):
    assert client.post("/api/emergency", json={"lane": "East"}).status_code == 200
    assert client.get("/api/stats").get_json()["emergency"] is True
    assert client.post("/api/emergency", json={"lane": "Nope"}).status_code == 400
    client.post("/api/emergency", json={"lane": None})
    assert client.get("/api/stats").get_json()["emergency"] is False


def test_lanes_api_validates_and_rebuilds(client):
    bad = client.post("/api/lanes", json=[{"name": "A", "points": [[0, 0]]}])
    assert bad.status_code == 400
    two = [{"name": "Left", "points": [[0, 0], [.5, 0], [.5, 1]]},
           {"name": "Right", "points": [[.5, 0], [1, 0], [1, 1]]}]
    assert client.post("/api/lanes", json=two).status_code == 200
    assert [l["name"] for l in client.get("/api/stats").get_json()["lanes"]] == ["Left", "Right"]
    assert client.post("/api/emergency", json={"lane": "East"}).status_code == 400   # old lane gone


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/calibrate").status_code == 200
    assert client.get("/snapshot.jpg").status_code == 503      # no frame before workers start
