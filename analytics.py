"""Count smoothing and the fixed-vs-adaptive wait comparison. Pure logic."""
from __future__ import annotations

import statistics
from collections import deque

import config


class CountSmoother:
    """Median over the last N detections per lane: removes single-frame flicker."""

    def __init__(self, names, window: int = config.SMOOTHING_WINDOW):
        self.hist = {n: deque(maxlen=window) for n in names}

    def add(self, counts: dict[str, int]) -> dict[str, int]:
        for n, h in self.hist.items():
            h.append(counts.get(n, 0))
        return {n: int(statistics.median_high(h)) for n, h in self.hist.items()}


class WaitMetrics:
    """Vehicle-seconds spent waiting at red under the adaptive controller vs a fixed timer,
    both fed the same measured counts."""

    def __init__(self):
        self.adaptive = self.fixed = self.elapsed = 0.0

    def add(self, counts, adaptive_states, fixed_states, dt: float) -> None:
        dt = min(max(dt, 0.0), 1.0)            # ignore stalls
        for name, c in counts.items():
            if adaptive_states.get(name) == "RED":
                self.adaptive += c * dt
            if fixed_states.get(name) == "RED":
                self.fixed += c * dt
        self.elapsed += dt

    def summary(self) -> dict:
        e = self.elapsed or 1.0
        enough = self.elapsed >= 10 and self.fixed > 0
        return {
            "elapsed": round(self.elapsed),
            "adaptive_avg_waiting": round(self.adaptive / e, 2),
            "fixed_avg_waiting": round(self.fixed / e, 2),
            "improvement_pct": round((self.fixed - self.adaptive) / self.fixed * 100, 1) if enough else None,
        }
