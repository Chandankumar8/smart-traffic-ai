"""Central settings. Override with environment variables where noted."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", str(BASE_DIR / "traffic.mp4"))
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "yolov8n.pt"))

# Detection
CONF_THRESHOLD = 0.35
INFER_SIZE = 416                   # smaller = faster (default YOLO size is 640)
SMOOTHING_WINDOW = 5               # detections averaged (median) to stop count flicker
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # COCO ids

# Lanes are polygons (normalised 0-1 points) stored in lanes.json and edited at /calibrate.
LANES_FILE = os.getenv("LANES_FILE", str(BASE_DIR / "lanes.json"))
MAX_LANES = 8

# Signal timing (seconds)
MIN_GREEN = 8
MAX_GREEN = 45
SECONDS_PER_VEHICLE = 2
YELLOW = 3
CONGESTION_THRESHOLD = 8           # vehicles in a lane considered "heavy"
FIXED_GREEN = 20                  # baseline fixed-timer green used for the comparison panel
