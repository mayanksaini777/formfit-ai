"""FORMFIT Phase 2 - movement intelligence.
Additive layer: phase, range-of-motion, tempo and movement-quality signals.
Does not replace pose_engine's core exercise rules or RepCounter.
"""
import time
from collections import deque


ANGLE_KEYS = {
    "squat": "knee",
    "lunges": "knee",
    "push_up": "elbow",
    "bicep_curls": "elbow",
    "tricep_extension": "elbow",
    "shoulder_press": "raise",
    "lateral_shoulder_raises": "raise",
}

class MovementIntelligence:
    def __init__(self):
        self.exercise = None
        self.reset()

    def reset(self, exercise=None):
        if exercise is not None:
            self.exercise = exercise
        self.values = deque(maxlen=24)
        self.times = deque(maxlen=24)
        self.min_value = None
        self.max_value = None
        self.phase = "READY"
        self.last_phase = "READY"
        self.last_transition = None
        self.cycles = 0

    def update(self, exercise, angles, score=0):
        if exercise != self.exercise:
            self.reset(exercise)

        key = ANGLE_KEYS.get(exercise)
        value = angles.get(key) if key else None
        now = time.monotonic()

        if value is None:
            return self._result(None, score, now)

        value = float(value)
        self.values.append(value)
        self.times.append(now)
        self.min_value = value if self.min_value is None else min(self.min_value, value)
        self.max_value = value if self.max_value is None else max(self.max_value, value)

        phase = self._phase(exercise, value)
        if phase != self.phase:
            self.last_phase = self.phase
            self.phase = phase
            self.last_transition = now
            if self.last_phase == "CONTRACTED" and phase == "EXTENDED":
                self.cycles += 1

        rom = max(0.0, (self.max_value or value) - (self.min_value or value))
        tempo = self._tempo(now)
        quality = self._quality(exercise, rom, tempo)

        return {
            "phase": self.phase,
            "angle": round(value, 1),
            "rom": round(rom, 1),
            "tempo_s": None if tempo is None else round(tempo, 2),
            "movement_quality": quality,
            "movement_cycles": self.cycles,
            "stable": len(self.values) >= 5,
        }

    def _phase(self, exercise, value):
        if exercise in {"squat", "lunges"}:
            if value <= 112:
                return "CONTRACTED"
            if value >= 140:
                return "EXTENDED"
        elif exercise in {"bicep_curls", "tricep_extension"}:
            if value <= 108:
                return "CONTRACTED"
            if value >= 130:
                return "EXTENDED"
        elif exercise == "push_up":
            if value <= 105:
                return "CONTRACTED"
            if value >= 145:
                return "EXTENDED"
        elif exercise in {"shoulder_press", "lateral_shoulder_raises"}:
            if value >= 65:
                return "CONTRACTED"
            if value <= 25:
                return "EXTENDED"
        return self.phase

    def _tempo(self, now):
        if self.last_transition is None:
            return None
        return max(0.0, now - self.last_transition)

    def _quality(self, exercise, rom, tempo):
        if len(self.values) < 5:
            return "CALIBRATING"
        if rom < 18:
            return "LOW_RANGE"
        if tempo is not None and tempo < 0.22:
            return "TOO_FAST"
        return "GOOD"

    def _result(self, value, score, now):
        return {
            "phase": self.phase,
            "angle": value,
            "rom": 0.0,
            "tempo_s": None,
            "movement_quality": "NO_DATA",
            "movement_cycles": self.cycles,
            "stable": False,
        }
