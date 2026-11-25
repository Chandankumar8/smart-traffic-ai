import pytest

from tracker import CentroidTracker, LaneMetrics


def test_ids_persist_and_expire():
    t = CentroidTracker(max_distance=50, max_missed=2)
    a = t.update([(10, 10, "N")])[0].id
    assert t.update([(20, 12, "N")])[0].id == a          # moved a little: same car
    assert t.update([(300, 300, "N")])[0].id != a        # far away: new car
    for _ in range(3):
        t.update([])
    assert t.tracks == {}


def test_wait_and_throughput():
    t, m = CentroidTracker(), LaneMetrics(["N"])
    for _ in range(4):                                   # 4 s waiting at red
        m.update(t.update([(5, 5, "N")]), {"N": "RED"}, 1.0)
    m.update(t.update([(5, 5, "N")]), {"N": "GREEN"}, 1.0)
    m.update(t.update([(5, 5, "N")]), {"N": "GREEN"}, 1.0)   # not double-counted
    assert m.snapshot()["N"] == {"avg_wait": pytest.approx(4.0), "throughput": 1}
