
"""
FORMFIT AI - LIVE FORM API V6
FULL REPLACEMENT.

Uses the exact pose_engine.py form rules.
Optimizations:
- binary JPEG upload instead of base64 JSON
- 360px processing width
- MediaPipe complexity 0 for live latency
- debug reloader OFF
- exact exercise analysis + rep counter preserved
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import cv2
import numpy as np
import threading
import time
import mediapipe as mp

import pose_engine as engine
import form_intelligence as intelligence

app = Flask(__name__)
CORS(app)

LOCK = threading.Lock()

STATE = {
    "exercise": "squat",
    "counter": engine.RepCounter(),
    "landmark_filter": engine.LandmarkSmoother(alpha=0.90),
    "decision_filter": engine.DecisionStabilizer(
        confirm_frames=2,
        release_frames=2,
    ),
    "target_filter": engine.TargetSmoother(alpha=0.90),
    "pose": None,
}


def make_pose():
    return mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=0,
        smooth_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.50,
        min_tracking_confidence=0.50,
    )


def ensure_pose():
    if STATE["pose"] is None:
        STATE["pose"] = make_pose()


def normalize(name):
    return engine.normalize_exercise(str(name or ""))


def decode_upload():
    raw = request.get_data(cache=False)
    if not raw:
        return None

    arr = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def reset_internal(exercise=None):
    if exercise:
        STATE["exercise"] = normalize(exercise)

    STATE["counter"].reset()
    STATE["landmark_filter"].reset()
    STATE["decision_filter"].reset()
    STATE["target_filter"].reset()


def np_point(point, width, height):
    return {
        "x": round(float(point[0]) / max(width, 1), 6),
        "y": round(float(point[1]) / max(height, 1), 6),
    }


def serialize(result, reps, width, height, elapsed_ms):
    pipes = []
    for a, b, status in result.pipes:
        pipes.append({
            "a": np_point(a, width, height),
            "b": np_point(b, width, height),
            "status": str(status),
        })

    targets = []
    for actual, desired, label in result.targets:
        targets.append({
            "actual": np_point(actual, width, height),
            "desired": np_point(desired, width, height),
            "label": str(label),
        })

    angles = {}
    for key, value in result.angles.items():
        if value is None:
            continue
        try:
            angles[str(key)] = round(float(value), 1)
        except (TypeError, ValueError):
            pass

    return {
        "detected": True,
        "exercise": STATE["exercise"],
        "exercise_name": engine.EXERCISES.get(
            STATE["exercise"], STATE["exercise"]
        ),
        "status": result.status,
        "message": result.message,
        "score": int(result.score),
        "reps": int(reps),
        "good_rep": bool(result.good_rep),
        "view": result.view,
        "angles": angles,
        "pipes": pipes,
        "targets": targets,
        "inference_ms": round(elapsed_ms, 1),
    }



class LandmarkProxy:
    __slots__ = ("x", "y", "z", "visibility", "presence")

    def __init__(self, item):
        self.x = float(item.get("x", 0.0))
        self.y = float(item.get("y", 0.0))
        self.z = float(item.get("z", 0.0))
        self.visibility = float(item.get("visibility", 1.0))
        self.presence = float(item.get("presence", 1.0))


def make_landmarks(payload):
    raw = payload.get("landmarks")
    if not isinstance(raw, list) or len(raw) < 33:
        return None
    try:
        return [LandmarkProxy(item) for item in raw[:33]]
    except (TypeError, ValueError, AttributeError):
        return None


@app.post("/api/analyze_landmarks")
def analyze_landmarks():
    """Low-latency V9 endpoint: browser MediaPipe -> exact form engine."""
    payload = request.get_json(silent=True) or {}
    exercise = normalize(payload.get("exercise", STATE["exercise"]))

    if exercise not in engine.EXERCISES:
        return jsonify({
            "error": "Exercise rule not available",
            "available": engine.EXERCISES,
        }), 400

    landmarks = make_landmarks(payload)
    if landmarks is None:
        return jsonify({
            "detected": False,
            "error": "Expected 33 pose landmarks",
        }), 400

    width = max(1, int(payload.get("width", 1280)))
    height = max(1, int(payload.get("height", 720)))

    with LOCK:
        if exercise != STATE["exercise"]:
            reset_internal(exercise)

        # Browser MediaPipe is already temporally smoothed. Python applies
        # only a very light second-pass smoother to prevent jitter without
        # introducing the old visible lag.
        landmarks = STATE["landmark_filter"].update(landmarks)

        raw_result = engine.analyze_exercise(
            STATE["exercise"],
            landmarks,
            width,
            height,
        )

        # Additive coaching layer: exercise-specific knowledge, explainable
        # issues and yellow correction targets. Core pipes, reps and dispatch
        # remain owned by pose_engine.py.
        raw_result = intelligence.enhance_result(
            raw_result,
            STATE["exercise"],
            landmarks,
            width,
            height,
        )

        result = engine.apply_stability(
            raw_result,
            STATE["decision_filter"],
            STATE["target_filter"],
        )

        reps = STATE["counter"].update(
            STATE["exercise"],
            result,
        )

        return jsonify({
            **serialize(result, reps, width, height, 0.0),
            "source": "browser_mediapipe",
        })


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "FORMFIT LIVE FORM API V6",
        "engine": "exact pose_engine.py + side rep fix",
        "exercise_count": len(engine.EXERCISES),
        "exercises": engine.EXERCISES,
    })


@app.post("/api/session")
def start_session():
    payload = request.get_json(silent=True) or {}
    exercise = normalize(payload.get("exercise", "squat"))

    if exercise not in engine.EXERCISES:
        return jsonify({
            "error": "Exercise rule not available",
            "available": engine.EXERCISES,
        }), 400

    with LOCK:
        reset_internal(exercise)

    return jsonify({
        "ok": True,
        "exercise": exercise,
        "name": engine.EXERCISES[exercise],
        "status": "READY",
    })


@app.post("/api/analyze")
def analyze_frame():
    exercise = normalize(
        request.args.get("exercise", STATE["exercise"])
    )

    if exercise not in engine.EXERCISES:
        return jsonify({
            "error": "Exercise rule not available"
        }), 400

    image = decode_upload()

    if image is None:
        return jsonify({"error": "Invalid JPEG frame"}), 400

    with LOCK:
        if exercise != STATE["exercise"]:
            reset_internal(exercise)

        ensure_pose()

        # Keep original mirrored-camera behavior.
        frame = cv2.flip(image, 1)

        # Limit work done by MediaPipe.
        h, w = frame.shape[:2]
        target_w = 360
        if w > target_w:
            target_h = max(1, int(h * target_w / w))
            frame = cv2.resize(
                frame,
                (target_w, target_h),
                interpolation=cv2.INTER_AREA,
            )

        height, width = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        started = time.perf_counter()
        results = STATE["pose"].process(rgb)
        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000.0

        if not results.pose_landmarks:
            return jsonify({
                "detected": False,
                "exercise": STATE["exercise"],
                "status": "red",
                "message": "BODY NOT DETECTED",
                "score": 0,
                "reps": int(STATE["counter"].reps),
                "pipes": [],
                "targets": [],
                "inference_ms": round(elapsed_ms, 1),
            })

        landmarks = STATE["landmark_filter"].update(
            results.pose_landmarks.landmark
        )

        raw_result = engine.analyze_exercise(
            STATE["exercise"],
            landmarks,
            width,
            height,
        )

        result = engine.apply_stability(
            raw_result,
            STATE["decision_filter"],
            STATE["target_filter"],
        )

        reps = STATE["counter"].update(
            STATE["exercise"],
            result,
        )

        return jsonify(
            serialize(
                result,
                reps,
                width,
                height,
                elapsed_ms,
            )
        )


if __name__ == "__main__":
    print("=" * 60)
    print("AI GYM FORMFIT - LIVE FORM API V6")
    print("FAST MODE + SIDE-VIEW REP COUNT FIX")
    print("API: http://127.0.0.1:5050")
    print("=" * 60)

    # Debug OFF: no reloader, no duplicate server process.
    app.run(
        host="127.0.0.1",
        port=5050,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
