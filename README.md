# 🚦 AI Smart Traffic Management System

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3-black?logo=flask)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-green?logo=opencv)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Object%20Detection-orange)
![Status](https://img.shields.io/badge/Status-Hackathon%20Project-success)

An adaptive traffic-signal prototype. It detects vehicles in a camera feed with YOLOv8, counts them per lane, and gives green time to the lanes that need it, instead of using a fixed timer. A live dashboard shows what it is doing and how it compares with a fixed-timer baseline.

---

## 📌 Problem

Fixed-time signals ignore real traffic. That means long waits on empty-road approaches, congestion at peak hours, wasted fuel, and no priority for emergency vehicles.

## ✨ What it does

| Feature | How it works |
|---|---|
| **Vehicle detection** | YOLOv8 finds cars, motorcycles, buses and trucks. Runs in its own thread so the video stays smooth. |
| **Lane zones you draw** | Draw one polygon per approach at `/calibrate`. A vehicle belongs to the lane containing its bottom-centre point. Saved to `lanes.json`. |
| **Stable counts** | A median over the last 5 detections removes single-frame flicker. |
| **Adaptive signals** | One green at a time, with a yellow phase. Green time grows with queue length (8–45 s). The busiest lane goes next. A lane that empties gives up its green early. |
| **Emergency priority** | Preempts the cycle (yellow, then green) for the chosen lane. **Simulated**: trigger it from the dashboard or the API (see below). |
| **Per-lane stats** | A centroid tracker gives each lane's average wait and number of vehicles served. |
| **Adaptive vs fixed** | A fixed 20 s timer runs on the same counts as a baseline. The dashboard shows average vehicles waiting at red for both. |

## 🏗️ Architecture

```text
 video file / camera
        │
        ▼
 stream thread ──► real-time playback, draws overlay, drives controllers
        │  ▲
 latest │  │ smoothed lane counts
 frame  ▼  │
 detector thread ──► YOLOv8 → lane assignment → smoothing → tracker
                                         │
                                         ▼
                 SignalController (adaptive)   FixedCycleController (baseline)
                                         │
                                         ▼
                  Flask: /video  /api/stats  /api/lanes  /api/emergency
                                         │
                                         ▼
                       Dashboard (index.html) + lane editor (calibrate.html)
```

## 📁 Project structure

```text
├── app.py                  # Flask app; video + detector worker threads
├── detector.py             # YOLOv8 wrapper and frame drawing
├── lanes.py                # Lane polygons: validation, lanes.json, detection → lane
├── signal_controller.py    # Adaptive controller + fixed-timer baseline
├── analytics.py            # Count smoothing, adaptive-vs-fixed wait metrics
├── tracker.py              # Centroid tracker + per-lane wait/throughput
├── config.py               # All tunables (timings, thresholds, model size)
├── templates/              # index.html (dashboard), calibrate.html (lane editor)
├── static/                 # style.css, dashboard.js, calibrate.js
├── tests/                  # pytest suite
├── .vscode/                # settings, launch configs, tasks
└── traffic.mp4, yolov8n.pt
```

## ⚙️ Setup

Requires Python 3.10+.

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

```bash
# Linux / macOS
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## ▶️ Run

```bash
python app.py
```

Open <http://127.0.0.1:5000>. In VS Code you can press **F5** and choose *Run Traffic App*.

1. Click **Edit lanes** (top right) and outline each approach on the frame, 3 or more points per lane. Click **Save lanes**.
2. Watch the dashboard: signal lights, countdown, per-lane counts and waits, and the adaptive-vs-fixed panel.
3. Try **Simulate emergency vehicle** and watch the chosen lane take the green.

Use your own footage or camera: `VIDEO_SOURCE=path/to/video.mp4` or `VIDEO_SOURCE=0` (webcam). On PowerShell: `$env:VIDEO_SOURCE="0"; python app.py`.

## 🔌 API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/stats` | GET | Signal state, per-lane counts / wait / throughput, comparison, FPS |
| `/api/lanes` | GET, POST | Read or replace lane polygons (validated, saved to `lanes.json`) |
| `/api/emergency` | POST | `{"lane": "East"}` to preempt, `{"lane": null}` to clear |
| `/snapshot.jpg` | GET | Latest raw frame (used by the lane editor) |
| `/video` | GET | MJPEG stream with overlay |
| `/health` | GET | `ok` or the current error message |

## 🔧 Tuning

Everything is in `config.py`: `MIN_GREEN`, `MAX_GREEN`, `SECONDS_PER_VEHICLE`, `YELLOW`, `CONF_THRESHOLD`, `INFER_SIZE` (lower = faster), `SMOOTHING_WINDOW`, `FIXED_GREEN`.

## 🧪 Tests

```bash
pytest -q
```

Covers the signal logic, emergency preemption, lane assignment, validation, smoothing, tracker, and the API routes.

## ⚠️ Limitations (please read before a demo)

- **Emergency detection is simulated.** Stock YOLOv8 cannot recognise ambulances or fire trucks. Automatic detection needs a custom-trained model (or siren detection).
- **The adaptive-vs-fixed result is an estimate.** Both controllers are fed the same recorded traffic, and a recorded video does not react to the signals. It shows how the policy behaves on that clip, not measured real-world improvement. The figure also fluctuates in the first minutes.
- **One camera, one intersection.** The "lanes" are zones in a single view. There is no multi-intersection coordination yet.
- **Lightweight tracker.** It is a simple nearest-neighbour tracker, so IDs can swap in dense traffic.
- **Development server.** `python app.py` runs Flask's dev server. Use a production WSGI server before any real deployment.

## 🚀 Roadmap

- History charts and CSV export of wait times
- Line-crossing throughput counts
- Custom-trained emergency-vehicle model
- Docker image with a production server
- Multi-intersection coordination

## 🖼️ Screenshots

><img width="1896" height="907" alt="image" src="https://github.com/user-attachments/assets/66a47337-6978-4ab6-be6d-61506f16c2a0" />


## 👤 Author

Built by **Chandan** (AI, backend and dashboard).

## 🔗 Links

- Presentation: _add link_
- Demo video: _add link_

## 📜 License

MIT. Add a `LICENSE` file to the repository root before publishing.
