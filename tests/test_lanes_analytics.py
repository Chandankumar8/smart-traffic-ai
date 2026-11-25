import sys
import types

import pytest

sys.modules.setdefault("ultralytics", types.ModuleType("ultralytics"))
import config
from analytics import CountSmoother, WaitMetrics
from detector import Detection
from lanes import DEFAULT_LANES, assign_lanes, load_lanes, save_lanes, validate_lanes
from signal_controller import FixedCycleController


def det(x1, y1, x2, y2):
    return Detection((x1, y1, x2, y2), "car", .9)


def test_assign_uses_bottom_centre_in_polygon():
    # bottom-centre of each box lands in a different quadrant of a 200x200 frame
    dets = [det(0, 0, 40, 40), det(160, 0, 200, 40), det(160, 120, 200, 160),
            det(0, 120, 40, 160), det(10, 10, 30, 30)]
    out = assign_lanes(dets, 200, 200, DEFAULT_LANES)
    assert {k: len(v) for k, v in out.items()} == {"North": 2, "East": 1, "South": 1, "West": 1}


def test_custom_polygon_and_outside_ignored():
    lanes = [{"name": "A", "points": [[0, 0], [.2, 0], [.2, 1], [0, 1]]},
             {"name": "B", "points": [[.2, 0], [.4, 0], [.4, 1], [.2, 1]]}]
    out = assign_lanes([det(0, 0, 20, 50), det(150, 0, 190, 50)], 100 * 2, 100, lanes)
    assert len(out["A"]) == 1 and len(out["B"]) == 0   # second box is right of both polygons


@pytest.mark.parametrize("bad", [
    None, [], [DEFAULT_LANES[0]],
    [{"name": "A", "points": [[0, 0], [1, 0]]}, {"name": "B", "points": [[0, 0], [1, 0], [1, 1]]}],
    [{"name": "A", "points": [[0, 0], [1, 0], [2, 1]]}, {"name": "B", "points": [[0, 0], [1, 0], [1, 1]]}],
    [{"name": "A", "points": [[0, 0], [1, 0], [1, 1]]}, {"name": "A", "points": [[0, 0], [1, 0], [1, 1]]}],
])
def test_validate_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        validate_lanes(bad)


def test_save_load_roundtrip_and_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LANES_FILE", str(tmp_path / "lanes.json"))
    assert load_lanes() == DEFAULT_LANES                 # missing file -> defaults
    save_lanes(validate_lanes(DEFAULT_LANES))
    assert [l["name"] for l in load_lanes()] == ["North", "East", "South", "West"]
    (tmp_path / "lanes.json").write_text("{not json")
    assert load_lanes() == DEFAULT_LANES                 # corrupt file -> defaults


def test_smoother_removes_single_frame_spike():
    s = CountSmoother(["N"], window=5)
    outs = [s.add({"N": v})["N"] for v in [4, 4, 12, 4, 4]]
    assert outs[-1] == 4


def test_wait_metrics_only_counts_red():
    m = WaitMetrics()
    for _ in range(20):
        m.add({"N": 4, "E": 6}, {"N": "GREEN", "E": "RED"}, {"N": "RED", "E": "GREEN"}, 1.0)
    s = m.summary()
    assert s["adaptive_avg_waiting"] == 6 and s["fixed_avg_waiting"] == 4
    assert s["improvement_pct"] == -50.0                 # fixed was better here; sign is honest


def test_fixed_controller_cycles():
    t = [0.0]
    f = FixedCycleController(["A", "B"], green=10, clock=lambda: t[0])
    assert f.states() == {"A": "GREEN", "B": "RED"}
    t[0] = 10.1; f.update()
    assert f.states()["A"] == "YELLOW"
    t[0] += config.YELLOW + .1; f.update()
    assert f.states() == {"A": "RED", "B": "GREEN"}
