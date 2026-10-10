"""Landmark observability and anatomical confidence layer.

Prevents FormFit from confidently judging body regions that the camera cannot
reliably see. This is intentionally additive: it does not change pose_engine.
"""
from __future__ import annotations

SEGMENT_IDS = {
    "left_arm": (11, 13, 15),
    "right_arm": (12, 14, 16),
    "left_leg": (23, 25, 27),
    "right_leg": (24, 26, 28),
    "left_torso": (11, 23),
    "right_torso": (12, 24),
}

EXERCISE_REQUIRED = {
    "bicep_curls": (11,12,13,14,15,16), "hammer_curl": (11,12,13,14,15,16),
    "tricep_extension": (11,12,13,14,15,16), "front_raise": (11,12,13,14,15,16),
    "lateral_shoulder_raises": (11,12,13,14,15,16), "shoulder_press": (11,12,13,14,15,16),
    "squat": (23,24,25,26,27,28), "lunges": (23,24,25,26,27,28),
    "reverse_lunge": (23,24,25,26,27,28), "step_up": (23,24,25,26,27,28),
    "calf_raise": (23,24,25,26,27,28), "deadlift": (11,12,23,24,25,26,27,28),
    "push_up": (11,12,23,24,27,28), "plank": (11,12,23,24,27,28),
}

class PoseObservability:
    def __init__(self, threshold=0.42):
        self.threshold = float(threshold)

    def _v(self, lm, i):
        try:
            return max(0.0, min(1.0, float(getattr(lm[i], "visibility", 0.0))))
        except Exception:
            return 0.0

    def update(self, exercise, landmarks):
        required = EXERCISE_REQUIRED.get(exercise)
        if not required:
            required = tuple(range(33))
        values = {str(i): round(self._v(landmarks, i), 3) for i in required}
        missing = [i for i in required if self._v(landmarks, i) < self.threshold]
        segments = {}
        for name, ids in SEGMENT_IDS.items():
            vals = [self._v(landmarks, i) for i in ids]
            segments[name] = round(min(vals), 3) if vals else 0.0
        overall = min(values.values()) if values else 0.0
        return {
            "overall": round(overall, 3),
            "required_count": len(required),
            "visible_count": len(required) - len(missing),
            "missing_landmarks": missing,
            "segments": segments,
            "reliable": not missing,
            "threshold": self.threshold,
        }
