"""FORMFIT live pose quality + calibration guard.

Additive safety/reliability layer. It does not change exercise rules or
rep thresholds. It only decides whether the current pose is reliable enough
for live coaching and repetition counting.
"""
import math
import statistics

import pose_engine as engine


COMMON = [
    engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER,
    engine.LEFT_HIP, engine.RIGHT_HIP,
]

REQUIRED = {
    "squat": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "lunges": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "reverse_lunge": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "step_up": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "deadlift": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "calf_raise": COMMON + [engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "glute_bridge": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE],
    "jumping_jack": COMMON + [engine.LEFT_WRIST, engine.RIGHT_WRIST, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "mountain_climber": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "burpee": COMMON + [engine.LEFT_KNEE, engine.RIGHT_KNEE, engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
    "push_up": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_HIP, engine.RIGHT_HIP,
                 engine.LEFT_ELBOW, engine.RIGHT_ELBOW, engine.LEFT_WRIST, engine.RIGHT_WRIST,
                 engine.LEFT_ANKLE, engine.RIGHT_ANKLE],
}

UPPER_BODY = {
    "bicep_curls": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_ELBOW, engine.RIGHT_ELBOW,
                     engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "hammer_curl": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_ELBOW, engine.RIGHT_ELBOW,
                     engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "lateral_shoulder_raises": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "front_raise": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "shoulder_press": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_ELBOW, engine.RIGHT_ELBOW,
                        engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "tricep_extension": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_ELBOW, engine.RIGHT_ELBOW,
                          engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "dumbbell_row": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_HIP, engine.RIGHT_HIP,
                      engine.LEFT_ELBOW, engine.RIGHT_ELBOW, engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "lat_pulldown": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_ELBOW, engine.RIGHT_ELBOW,
                      engine.LEFT_WRIST, engine.RIGHT_WRIST],
    "close_grip_lat_pulldown": [engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER, engine.LEFT_ELBOW, engine.RIGHT_ELBOW,
                                 engine.LEFT_WRIST, engine.RIGHT_WRIST],
}


class PoseQuality:
    """Per-session quality estimator with a short missing-pose grace period."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.ema = None
        self.reference_scale = None
        self.good_frames = 0
        self.missing_frames = 0

    @staticmethod
    def _visible(lm, idx, threshold=0.45):
        try:
            p = float(lm[idx].visibility)
            return p >= threshold and math.isfinite(float(lm[idx].x)) and math.isfinite(float(lm[idx].y))
        except Exception:
            return False

    def _required(self, exercise):
        if exercise in REQUIRED:
            return REQUIRED[exercise]
        return UPPER_BODY.get(exercise, COMMON)

    def _scale(self, lm, exercise):
        def d(a, b):
            if not (self._visible(lm, a) and self._visible(lm, b)):
                return None
            return engine.distance(
                engine.xy(lm, a, 1, 1),
                engine.xy(lm, b, 1, 1),
            )

        shoulder = d(engine.LEFT_SHOULDER, engine.RIGHT_SHOULDER)
        hip = d(engine.LEFT_HIP, engine.RIGHT_HIP)
        torso_l = d(engine.LEFT_SHOULDER, engine.LEFT_HIP)
        torso_r = d(engine.RIGHT_SHOULDER, engine.RIGHT_HIP)

        vals = [v for v in (shoulder, hip, torso_l, torso_r) if v and v > 0]
        if exercise not in UPPER_BODY:
            # Add leg scale for full-body movements.
            leg_l = d(engine.LEFT_HIP, engine.LEFT_ANKLE)
            leg_r = d(engine.RIGHT_HIP, engine.RIGHT_ANKLE)
            vals.extend(v for v in (leg_l, leg_r) if v and v > 0)
        return statistics.median(vals) if vals else None

    def update(self, landmarks, exercise):
        required = self._required(exercise)
        visible_items = [i for i in required if self._visible(landmarks, i)]
        coverage = len(visible_items) / max(len(required), 1)
        visibility = (
            sum(float(landmarks[i].visibility) for i in visible_items) / len(visible_items)
            if visible_items else 0.0
        )

        scale = self._scale(landmarks, exercise)
        scale_score = 0.0
        if scale is not None:
            if self.reference_scale is None and coverage >= 0.75 and visibility >= 0.65:
                self.reference_scale = scale
            if self.reference_scale:
                ratio = scale / max(self.reference_scale, 1e-6)
                if 0.72 <= ratio <= 1.32:
                    scale_score = 100.0
                elif 0.55 <= ratio <= 1.55:
                    scale_score = 70.0
                else:
                    scale_score = 35.0
            else:
                scale_score = 85.0

        raw = 0.62 * coverage * 100 + 0.28 * visibility * 100 + 0.10 * scale_score
        if self.ema is None:
            self.ema = raw
        else:
            self.ema = 0.25 * raw + 0.75 * self.ema

        if coverage < 0.45 or visibility < 0.42:
            self.missing_frames += 1
        else:
            self.missing_frames = 0
            self.good_frames += 1

        if self.missing_frames >= 3:
            state = "lost"
            message = "MOVE INTO FRAME"
            reason = "body_visibility"
        elif self.ema < 62:
            state = "warning"
            message = "SHOW YOUR FULL BODY CLEARLY"
            reason = "low_pose_confidence"
        elif scale_score and scale_score < 70:
            state = "warning"
            message = "MOVE A LITTLE CLOSER OR FARTHER"
            reason = "camera_distance"
        else:
            state = "ready"
            message = "POSE LOCKED"
            reason = "ok"

        # Do not claim a calibrated pose until we have enough stable frames.
        calibrated = self.good_frames >= 10 and self.reference_scale is not None
        rep_ready = state != "lost" and self.ema >= 55 and (calibrated or self.good_frames >= 3)

        return {
            "state": state,
            "score": int(round(max(0, min(100, self.ema)))),
            "coverage": round(coverage, 3),
            "visibility": round(visibility, 3),
            "calibrated": bool(calibrated),
            "rep_ready": bool(rep_ready),
            "message": message,
            "reason": reason,
        }
