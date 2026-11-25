"""Lightweight centroid tracker + per-lane wait/throughput metrics. Pure Python."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Track:
    id: int
    pos: tuple[int, int]
    lane: str | None
    missed: int = 0
    wait: float = 0.0           # seconds spent in a RED lane
    served: bool = False        # seen in a lane while it was GREEN


class CentroidTracker:
    def __init__(self, max_distance: float = 80, max_missed: int = 5):
        self.max_distance, self.max_missed = max_distance, max_missed
        self.tracks: dict[int, Track] = {}
        self._next = 1

    def update(self, points: list[tuple[int, int, str | None]]) -> list[Track]:
        """points: (cx, cy, lane). Greedy nearest-neighbour matching."""
        pairs = sorted(
            (math.dist(t.pos, (x, y)), tid, i)
            for tid, t in self.tracks.items() for i, (x, y, _) in enumerate(points))
        used_t, used_p, matched = set(), set(), []
        for d, tid, i in pairs:
            if d > self.max_distance or tid in used_t or i in used_p:
                continue
            used_t.add(tid); used_p.add(i)
            t = self.tracks[tid]
            t.pos, t.lane, t.missed = points[i][:2], points[i][2], 0
            matched.append(t)
        for tid in set(self.tracks) - used_t:
            self.tracks[tid].missed += 1
        for i, (x, y, lane) in enumerate(points):
            if i not in used_p:
                t = Track(self._next, (x, y), lane)
                self.tracks[t.id] = t; matched.append(t); self._next += 1
        self.tracks = {k: t for k, t in self.tracks.items() if t.missed <= self.max_missed}
        return matched


@dataclass
class LaneMetrics:
    lanes: list[str]
    waits: dict[str, list[float]] = field(default_factory=dict)
    served: dict[str, set[int]] = field(default_factory=dict)

    def __post_init__(self):
        self.waits = {n: [] for n in self.lanes}
        self.served = {n: set() for n in self.lanes}

    def update(self, tracks: list[Track], states: dict[str, str], dt: float) -> None:
        for t in tracks:
            if t.lane is None:
                continue
            if states[t.lane] == "RED":
                t.wait += dt
            elif states[t.lane] == "GREEN" and t.id not in self.served[t.lane]:
                self.served[t.lane].add(t.id)
                self.waits[t.lane].append(t.wait)      # wait endured before release

    def snapshot(self) -> dict:
        out = {}
        for n in self.lanes:
            w = self.waits[n]
            out[n] = {"avg_wait": round(sum(w) / len(w), 1) if w else 0.0,
                      "throughput": len(self.served[n])}
        return out
