"""Flask app.

Two background threads keep the video smooth even when YOLO is slow:
  * stream_worker   - plays the video in real time, drives the signal controllers, draws + encodes
  * detector_worker - runs YOLO on the newest frame as fast as it can and publishes smoothed counts
HTTP routes only read shared state under `lock`.
"""
from __future__ import annotations

import logging
import threading
import time

import cv2
from flask import Flask, Response, jsonify, render_template, request

import config
from analytics import CountSmoother, WaitMetrics
from detector import VehicleDetector, draw
from lanes import assign_lanes, load_lanes, save_lanes, validate_lanes
from signal_controller import FixedCycleController, SignalController
from tracker import CentroidTracker, LaneMetrics

log = logging.getLogger("traffic")
app = Flask(__name__)
lock = threading.RLock()

lanes: list[dict] = load_lanes()
controller = fixed = smoother = metrics = tracker = lane_metrics = None
state = {"jpeg": None, "raw": None, "snapshot": {}, "fps": 0.0, "error": None,
         "detections": [], "counts": {}, "tracks": []}


def apply_lanes(new_lanes: list[dict]) -> None:
    """(Re)build everything that depends on the lane list. Caller must not hold stale refs."""
    global lanes, controller, fixed, smoother, metrics, tracker, lane_metrics
    names = [l["name"] for l in new_lanes]
    with lock:
        lanes = new_lanes
        controller, fixed = SignalController(names), FixedCycleController(names)
        smoother, metrics = CountSmoother(names), WaitMetrics()
        tracker, lane_metrics = CentroidTracker(), LaneMetrics(names)
        state["tracks"] = []
        state["counts"] = {n: 0 for n in names}
        state["detections"] = []
        state["snapshot"] = build_snapshot()


def build_snapshot() -> dict:
    """Controller snapshot + per-lane wait/throughput + adaptive-vs-fixed comparison."""
    snap = controller.snapshot()
    per_lane = lane_metrics.snapshot()
    for lane in snap["lanes"]:
        lane.update(per_lane[lane["name"]])
    snap["comparison"] = metrics.summary()
    return snap


apply_lanes(lanes)


def open_capture():
    src = config.VIDEO_SOURCE
    cap = cv2.VideoCapture(int(src) if str(src).isdigit() else src)
    if not cap.isOpened():
        state["error"] = f"Cannot open video source: {src}"
        return None
    return cap


def stream_worker():
    cap = open_capture()
    if cap is None:
        return
    delay = 1 / (cap.get(cv2.CAP_PROP_FPS) or 25)
    last, fps = time.monotonic(), 0.0
    while True:
        t0 = time.monotonic()
        ok, frame = cap.read()
        if not ok:                                   # loop the video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        with lock:
            state["raw"] = frame
            dets, counts, cur_lanes = list(state["detections"]), dict(state["counts"]), lanes
            controller.update(counts)
            fixed.update(counts)
            metrics.add(counts, controller.states(), fixed.states(), t0 - last)
            lane_metrics.update(state["tracks"], controller.states(), min(t0 - last, 1.0))
            snap = build_snapshot()
        view = frame.copy()                          # `raw` stays unannotated for /snapshot.jpg
        draw(view, dets, snap, cur_lanes)
        _, buf = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 80])
        fps = 0.9 * fps + 0.1 / max(t0 - last, 1e-6)
        last = t0
        with lock:
            state.update(jpeg=buf.tobytes(), snapshot=snap, fps=round(fps, 1))
        time.sleep(max(0.0, delay - (time.monotonic() - t0)))


def detector_worker():
    try:
        detector = VehicleDetector()
    except Exception as exc:                          # e.g. ultralytics missing
        log.exception("detector failed to load")
        state["error"] = f"Detector failed to load: {exc}"
        return
    last_frame = None
    while True:
        with lock:
            frame, cur = state["raw"], lanes
        if frame is None or frame is last_frame:
            time.sleep(0.01)
            continue
        last_frame = frame
        dets = detector.detect(frame)
        h, w = frame.shape[:2]
        per_lane = assign_lanes(dets, w, h, cur)
        with lock:
            if cur is lanes:                          # lanes weren't edited meanwhile
                state["detections"] = dets
                points = [((d.box[0] + d.box[2]) // 2, d.box[3], name)
                          for name, ds in per_lane.items() for d in ds]
                state["tracks"] = tracker.update(points)
                state["counts"] = smoother.add({n: len(v) for n, v in per_lane.items()})


def mjpeg():
    while True:
        with lock:
            jpeg = state["jpeg"]
        if jpeg:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        time.sleep(0.04)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/calibrate")
def calibrate():
    return render_template("calibrate.html")


@app.route("/video")
def video():
    return Response(mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/snapshot.jpg")
def snapshot_jpg():
    with lock:
        raw = state["raw"]
    if raw is None:
        return jsonify(error="no frame yet"), 503
    _, buf = cv2.imencode(".jpg", raw)
    return Response(buf.tobytes(), mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@app.route("/api/stats")
def stats():
    with lock:
        return jsonify(**state["snapshot"], fps=state["fps"], error=state["error"])


@app.route("/api/lanes", methods=["GET", "POST"])
def api_lanes():
    if request.method == "GET":
        with lock:
            return jsonify(lanes)
    try:
        new = validate_lanes(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    save_lanes(new)
    apply_lanes(new)
    return jsonify(ok=True, lanes=new)


@app.route("/api/emergency", methods=["POST"])
def emergency():
    """Simulate an emergency vehicle: POST {"lane": "East"} or {"lane": null} to clear."""
    lane = (request.get_json(silent=True) or {}).get("lane")
    with lock:
        if lane is not None and lane not in controller.lanes:
            return jsonify(error=f"unknown lane {lane!r}", lanes=controller.lanes), 400
        controller.set_emergency(lane)
        state["snapshot"] = build_snapshot()        # instant feedback, not next frame
    return jsonify(ok=True, lane=lane)


@app.route("/health")
def health():
    return jsonify(status="error" if state["error"] else "ok", error=state["error"])


def start_workers():
    for fn in (stream_worker, detector_worker):
        threading.Thread(target=fn, daemon=True, name=fn.__name__).start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_workers()
    # use_reloader=False so the worker threads aren't started twice
    app.run(debug=True, use_reloader=False, threaded=True)
