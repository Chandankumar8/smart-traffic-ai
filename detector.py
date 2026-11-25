"""YOLOv8 vehicle detector. Importing this module has no side effects."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

import config


@dataclass
class Detection:
    box: tuple[int, int, int, int]
    label: str
    conf: float

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.box
        return (x1 + x2) // 2, (y1 + y2) // 2


class VehicleDetector:
    def __init__(self, model_path: str = config.MODEL_PATH):
        from ultralytics import YOLO  # lazy: keeps import fast, eases testing
        self.model = YOLO(model_path)

    def detect(self, frame) -> list[Detection]:
        result = self.model.predict(
            frame, conf=config.CONF_THRESHOLD, imgsz=config.INFER_SIZE,
            classes=list(config.VEHICLE_CLASSES), verbose=False)[0]
        return [
            Detection(tuple(map(int, b.xyxy[0])),
                      config.VEHICLE_CLASSES[int(b.cls[0])], float(b.conf[0]))
            for b in result.boxes
        ]


def draw(frame, detections: list[Detection], snapshot: dict, lanes: list[dict]):
    h, w = frame.shape[:2]
    colors = {"GREEN": (80, 200, 80), "YELLOW": (0, 210, 255), "RED": (60, 60, 230)}
    for lane, info in zip(lanes, snapshot["lanes"]):
        c = colors[info["state"]]
        pts = np.array([[x * w, y * h] for x, y in lane["points"]], np.int32)
        cv2.polylines(frame, [pts], True, c, 2)
        cv2.putText(frame, f"{lane['name']}: {info['count']}", tuple(int(v) for v in pts[0] + [8, 24]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    for d in detections:
        cv2.rectangle(frame, d.box[:2], d.box[2:], (0, 255, 0), 1)
    return frame


if __name__ == "__main__":      # quick standalone test: python detector.py
    det = VehicleDetector()
    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        dets = det.detect(frame)
        for d in dets:
            cv2.rectangle(frame, d.box[:2], d.box[2:], (0, 255, 0), 2)
        cv2.imshow("Vehicle Detection (q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
