"""Adaptive signal controller. Pure logic: no OpenCV/YOLO, so it is easy to test."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import config


def green_duration(count: int) -> int:
    """Green time grows with queue length, clamped to [MIN_GREEN, MAX_GREEN]."""
    return max(config.MIN_GREEN,
               min(config.MAX_GREEN, config.MIN_GREEN + count * config.SECONDS_PER_VEHICLE))


@dataclass
class SignalController:
    lanes: list[str]
    clock: Callable[[], float] = time.monotonic
    active: int = 0
    phase: str = "GREEN"            # GREEN or YELLOW (all other lanes are RED)
    phase_end: float = 0.0
    phase_start: float = 0.0
    emergency_lane: int | None = None
    counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.counts = {n: 0 for n in self.lanes}
        self.phase_start = self.clock()
        self.phase_end = self.phase_start + config.MIN_GREEN

    # -- inputs -----------------------------------------------------------
    def set_emergency(self, lane: str | None) -> None:
        self.emergency_lane = None if lane is None else self.lanes.index(lane)

    def update(self, counts: dict[str, int]) -> None:
        """Feed latest per-lane counts and advance the state machine."""
        self.counts.update(counts)
        now = self.clock()

        # Emergency preempts everything: go yellow then switch immediately.
        if self.emergency_lane is not None and self.active != self.emergency_lane:
            if self.phase == "GREEN":
                self.phase, self.phase_start, self.phase_end = "YELLOW", now, now + config.YELLOW
            if now >= self.phase_end:
                self._switch_to(self.emergency_lane, now)
            return
        if self.emergency_lane is not None:      # emergency lane already green: hold
            self.phase, self.phase_end = "GREEN", now + config.MIN_GREEN
            return

        if now < self.phase_end:
            # Early cut-off: lane has emptied (after its minimum green) while others wait.
            served = now - self.phase_start
            if not (self.phase == "GREEN" and served >= config.MIN_GREEN
                    and self.counts[self.lanes[self.active]] == 0
                    and max(self.counts.values()) > 0):
                return
        if self.phase == "GREEN":
            self.phase, self.phase_start, self.phase_end = "YELLOW", now, now + config.YELLOW
        else:
            self._switch_to(self._busiest_other(), now)

    # -- internals --------------------------------------------------------
    def _busiest_other(self) -> int:
        n = len(self.lanes)
        order = [(self.active + i) % n for i in range(1, n + 1)]   # round-robin tie-break
        return max(order, key=lambda i: self.counts[self.lanes[i]])

    def _switch_to(self, idx: int, now: float) -> None:
        self.active, self.phase, self.phase_start = idx, "GREEN", now
        self.phase_end = now + green_duration(self.counts[self.lanes[idx]])

    # -- outputs ----------------------------------------------------------
    def states(self) -> dict[str, str]:
        return {n: (self.phase if i == self.active else "RED") for i, n in enumerate(self.lanes)}

    def snapshot(self) -> dict:
        now = self.clock()
        lanes = []
        for i, name in enumerate(self.lanes):
            state = (self.phase if i == self.active else "RED")
            lanes.append({
                "name": name,
                "count": self.counts[name],
                "state": state,
                "congested": self.counts[name] >= config.CONGESTION_THRESHOLD,
                "emergency": self.emergency_lane == i,
            })
        return {
            "lanes": lanes,
            "active": self.lanes[self.active],
            "phase": self.phase,
            "remaining": max(0, round(self.phase_end - now)),
            "emergency": self.emergency_lane is not None,
            "total": sum(self.counts.values()),
        }


class FixedCycleController:
    """Baseline: every lane gets the same green in turn, ignoring traffic."""

    def __init__(self, lanes: list[str], green: float = config.FIXED_GREEN,
                 clock: Callable[[], float] = time.monotonic):
        self.lanes, self.green, self.clock = lanes, green, clock
        self.active, self.phase = 0, "GREEN"
        self.phase_end = clock() + green

    def update(self, counts=None) -> None:
        now = self.clock()
        if now < self.phase_end:
            return
        if self.phase == "GREEN":
            self.phase, self.phase_end = "YELLOW", now + config.YELLOW
        else:
            self.active, self.phase = (self.active + 1) % len(self.lanes), "GREEN"
            self.phase_end = now + self.green

    def states(self) -> dict[str, str]:
        return {n: (self.phase if i == self.active else "RED") for i, n in enumerate(self.lanes)}
