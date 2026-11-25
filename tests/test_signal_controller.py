import pytest

import config
from signal_controller import SignalController, green_duration

LANES = ["N", "E", "S", "W"]


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t


def make():
    clk = Clock()
    return SignalController(LANES, clock=clk), clk


def test_green_duration_clamped():
    assert green_duration(0) == config.MIN_GREEN
    assert green_duration(1000) == config.MAX_GREEN


def test_busiest_lane_gets_next_green():
    c, clk = make()
    counts = {"N": 2, "E": 1, "S": 9, "W": 3}
    clk.t = config.MIN_GREEN + 0.1
    c.update(counts)                       # N green ends -> yellow
    assert c.phase == "YELLOW"
    clk.t += config.YELLOW + 0.1
    c.update(counts)
    assert (c.active, c.phase) == (2, "GREEN")
    assert c.phase_end - clk.t == pytest.approx(green_duration(9))


def test_only_one_lane_green_at_a_time():
    c, _ = make()
    c.update({"N": 1, "E": 1, "S": 1, "W": 1})
    states = [l["state"] for l in c.snapshot()["lanes"]]
    assert states.count("GREEN") == 1 and states.count("RED") == 3


def test_emergency_preempts_after_yellow():
    c, clk = make()
    c.set_emergency("W")
    c.update({"N": 5, "E": 0, "S": 0, "W": 0})
    assert c.phase == "YELLOW"
    clk.t += config.YELLOW + 0.1
    c.update({"N": 5, "E": 0, "S": 0, "W": 0})
    assert c.lanes[c.active] == "W" and c.phase == "GREEN"


def test_emergency_lane_held_green_then_released():
    c, clk = make()
    c.set_emergency("N")                   # already active lane
    clk.t = 100
    c.update({"N": 0, "E": 9, "S": 0, "W": 0})
    assert c.active == 0 and c.phase == "GREEN"
    c.set_emergency(None)
    assert not c.snapshot()["emergency"]


def test_early_cutoff_when_lane_empties():
    c, clk = make()
    c.counts["N"] = 30
    c._switch_to(0, clk.t)                 # long green for N
    clk.t += config.MIN_GREEN + 1
    c.update({"N": 0, "E": 4, "S": 0, "W": 0})
    assert c.phase == "YELLOW"


def test_snapshot_flags_congestion():
    c, _ = make()
    c.update({"N": config.CONGESTION_THRESHOLD, "E": 0, "S": 0, "W": 0})
    assert c.snapshot()["lanes"][0]["congested"]
