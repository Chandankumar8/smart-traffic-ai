"""Lane polygons: defaults, validation, persistence and detection->lane assignment."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import config

DEFAULT_LANES = [
    {"name": "North", "points": [[0, 0], [.5, 0], [.5, .5], [0, .5]]},
    {"name": "East",  "points": [[.5, 0], [1, 0], [1, .5], [.5, .5]]},
    {"name": "South", "points": [[.5, .5], [1, .5], [1, 1], [.5, 1]]},
    {"name": "West",  "points": [[0, .5], [.5, .5], [.5, 1], [0, 1]]},
]


def validate_lanes(data) -> list[dict]:
    """Return a cleaned lane list or raise ValueError with a readable message."""
    if not isinstance(data, list) or not 2 <= len(data) <= config.MAX_LANES:
        raise ValueError(f"need between 2 and {config.MAX_LANES} lanes")
    clean, seen = [], set()
    for lane in data:
        name = str(lane.get("name", "")).strip()[:20]
        if not name or name in seen:
            raise ValueError("lane names must be unique and non-empty")
        seen.add(name)
        pts = lane.get("points", [])
        if len(pts) < 3:
            raise ValueError(f"lane {name!r} needs at least 3 points")
        try:
            pts = [[float(x), float(y)] for x, y in pts]
        except (TypeError, ValueError):
            raise ValueError(f"lane {name!r} has invalid points") from None
        if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in pts):
            raise ValueError(f"lane {name!r} has points outside the frame")
        clean.append({"name": name, "points": pts})
    return clean


def load_lanes() -> list[dict]:
    try:
        return validate_lanes(json.loads(Path(config.LANES_FILE).read_text()))
    except (OSError, ValueError, TypeError, AttributeError):
        return [dict(l) for l in DEFAULT_LANES]


def save_lanes(lanes: list[dict]) -> None:
    Path(config.LANES_FILE).write_text(json.dumps(lanes, indent=2))


def assign_lanes(detections, width: int, height: int, lanes: list[dict]) -> dict[str, list]:
    """Group detections by lane. A vehicle's ground position is its bottom-centre point."""
    polys = {l["name"]: np.array([[x * width, y * height] for x, y in l["points"]], np.float32)
             for l in lanes}
    out = {name: [] for name in polys}
    for d in detections:
        x1, _, x2, y2 = d.box
        pt = ((x1 + x2) / 2, float(y2))
        for name, poly in polys.items():
            if cv2.pointPolygonTest(poly, pt, False) >= 0:
                out[name].append(d)
                break
    return out
