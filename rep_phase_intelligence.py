"""Temporal exercise phase validation for FormFit.

Prevents a single angle threshold from becoming a repetition. The validator
requires a plausible start -> contraction/depth -> return sequence before it
allows the existing pose_engine RepCounter to progress.
"""
from __future__ import annotations

class RepPhaseIntelligence:
    PROFILES = {
        # key, start condition, active condition, return condition, direction
        "bicep_curls": ("elbow", lambda v: v >= 135, lambda v: v <= 100, lambda v: v >= 135, "high_low_high"),
        "hammer_curl": ("elbow", lambda v: v >= 135, lambda v: v <= 100, lambda v: v >= 135, "high_low_high"),
        "squat": ("knee", lambda v: v >= 145, lambda v: v <= 112, lambda v: v >= 145, "high_low_high"),
        "lunges": ("knee", lambda v: v >= 145, lambda v: v <= 112, lambda v: v >= 145, "high_low_high"),
        "reverse_lunge": ("knee", lambda v: v >= 150, lambda v: v <= 105, lambda v: v >= 150, "high_low_high"),
        "step_up": ("knee", lambda v: v >= 155, lambda v: v <= 100, lambda v: v >= 155, "high_low_high"),
        "deadlift": ("knee", lambda v: v >= 150, lambda v: v <= 108, lambda v: v >= 150, "high_low_high"),
        "push_up": ("elbow", lambda v: v >= 145, lambda v: v <= 105, lambda v: v >= 145, "high_low_high"),
        "push_up_wide_grip": ("elbow", lambda v: v >= 145, lambda v: v <= 105, lambda v: v >= 145, "high_low_high"),
        "push_up_diamond": ("elbow", lambda v: v >= 145, lambda v: v <= 105, lambda v: v >= 145, "high_low_high"),
        "incline_push_up": ("elbow", lambda v: v >= 145, lambda v: v <= 105, lambda v: v >= 145, "high_low_high"),
        "decline_push_up": ("elbow", lambda v: v >= 145, lambda v: v <= 105, lambda v: v >= 145, "high_low_high"),
        "dumbbell_row": ("elbow", lambda v: v >= 145, lambda v: v <= 75, lambda v: v >= 145, "high_low_high"),
        "lat_pulldown": ("elbow", lambda v: v >= 145, lambda v: v <= 95, lambda v: v >= 145, "high_low_high"),
        "close_grip_lat_pulldown": ("elbow", lambda v: v >= 145, lambda v: v <= 95, lambda v: v >= 145, "high_low_high"),
        "bench_press": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "incline_dumbbell_press": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "decline_bench_press": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "incline_bench_press": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "dumbbell_bench_press": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "close_grip_bench_press": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "chest_press_machine": ("elbow", lambda v: v >= 150, lambda v: v <= 115, lambda v: v >= 150, "high_low_high"),
        "shoulder_press": ("elbow", lambda v: v <= 100, lambda v: v >= 150, lambda v: v <= 100, "low_high_low"),
        "tricep_extension": ("elbow", lambda v: v <= 80, lambda v: v >= 145, lambda v: v <= 80, "low_high_low"),
        "lateral_shoulder_raises": ("raise", lambda v: v <= 28, lambda v: v >= 65, lambda v: v <= 28, "low_high_low"),
        "front_raise": ("raise", lambda v: v <= 30, lambda v: v >= 70, lambda v: v <= 30, "low_high_low"),
        "chest_fly": ("fly", lambda v: v <= .35, lambda v: v >= 1.25, lambda v: v <= .35, "low_high_low"),
        "cable_crossover": ("fly", lambda v: v <= .35, lambda v: v >= 1.25, lambda v: v <= .35, "low_high_low"),
        "low_cable_crossover": ("fly", lambda v: v <= .35, lambda v: v >= 1.25, lambda v: v <= .35, "low_high_low"),
        "glute_bridge": ("hip", lambda v: v <= 118, lambda v: v >= 155, lambda v: v <= 118, "low_high_low"),
        "mountain_climber": ("knee_drive", lambda v: v >= 160, lambda v: v <= 95, lambda v: v >= 160, "high_low_high"),
        "burpee": ("knee", lambda v: v >= 155, lambda v: v <= 100, lambda v: v >= 155, "high_low_high"),
        "calf_raise": ("calf", lambda v: v <= 1.00, lambda v: v >= 1.10, lambda v: v <= 1.00, "low_high_low"),
    }

    def __init__(self):
        self.exercise = None
        self.phase = "WAIT_START"
        self.cycles = 0
        self.last_value = None
        self.last_reason = ""

    def reset(self, exercise):
        self.exercise = exercise
        self.phase = "WAIT_START"
        self.cycles = 0
        self.last_value = None
        self.last_reason = ""

    def update(self, exercise, angles, compatible=True):
        if exercise != self.exercise:
            self.reset(exercise)
        profile = self.PROFILES.get(exercise)
        if not profile:
            return {"phase": "UNTRACKED", "rep_ready": bool(compatible), "cycle_ready": False, "cycles": self.cycles, "reason": ""}
        key, start_fn, active_fn, return_fn, direction = profile
        value = (angles or {}).get(key)
        if value is None or not compatible:
            self.last_reason = "Exercise position is not valid enough to track the repetition."
            return {"phase": self.phase, "rep_ready": False, "cycle_ready": False, "cycles": self.cycles, "reason": self.last_reason}

        # State machine deliberately requires the start posture before a cycle.
        if self.phase == "WAIT_START":
            if start_fn(value):
                self.phase = "START"
            self.last_value = value
            return {"phase": self.phase, "rep_ready": True, "cycle_ready": False, "cycles": self.cycles, "reason": "" if self.phase == "START" else "Return to the exercise start position."}

        if direction == "high_low_high":
            if self.phase == "START" and active_fn(value):
                self.phase = "ACTIVE"
            elif self.phase == "ACTIVE" and return_fn(value):
                self.phase = "START"
                self.cycles += 1
            # A return to start without reaching the active range is not a rep.
        else:
            if self.phase == "START" and active_fn(value):
                self.phase = "ACTIVE"
            elif self.phase == "ACTIVE" and return_fn(value):
                self.phase = "START"
                self.cycles += 1

        self.last_value = value
        return {"phase": self.phase, "rep_ready": True, "cycle_ready": self.cycles > 0, "cycles": self.cycles, "reason": ""}

    def snapshot(self):
        return {"exercise": self.exercise, "phase": self.phase, "cycles": self.cycles, "last_value": self.last_value, "reason": self.last_reason}
