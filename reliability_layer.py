"""Human-motion reliability layer.

FormFit should not punish a user for one noisy frame or a small natural
variation.  Advanced exercise errors become actionable only after they are
persistent enough to be meaningful.  This layer is deliberately exercise-
agnostic and sits between biomechanical detection and visual/rep decisions.
"""
from __future__ import annotations

from collections import defaultdict


class ReliabilityLayer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.exercise = None
        self.counts = defaultdict(int)
        self.missed = defaultdict(int)
        self.frame = 0

    def start(self, exercise):
        self.reset()
        self.exercise = str(exercise or "")

    @staticmethod
    def _required(issue):
        priority = str(issue.get("priority", "medium")).lower()
        # A single frame is never enough to turn a human-motion variation red.
        return {"high": 4, "medium": 6, "low": 8}.get(priority, 6)

    @staticmethod
    def _severity(issue):
        return str(issue.get("priority", "medium")).lower()

    def update(self, exercise, issues, *, observable=True):
        exercise = str(exercise or "")
        if exercise != self.exercise:
            self.start(exercise)
        self.frame += 1

        current = {str(i.get("code")): i for i in (issues or []) if i.get("code")}

        # Advance persistence for seen issues and decay issues that disappear.
        for code in list(set(self.counts) | set(current)):
            if code in current:
                self.counts[code] += 1
                self.missed[code] = 0
            else:
                self.missed[code] += 1
                # Forget quickly after a clean run; this prevents stale red.
                if self.missed[code] >= 3:
                    self.counts[code] = max(0, self.counts[code] - 2)
                if self.missed[code] >= 8:
                    self.counts.pop(code, None)
                    self.missed.pop(code, None)

        confirmed = []
        warnings = []
        for code, item in current.items():
            n = self.counts.get(code, 0)
            needed = self._required(item)
            if n >= needed:
                confirmed.append(dict(item))
            else:
                pending = dict(item)
                pending["priority"] = "low"
                pending["pending"] = True
                pending["frames_seen"] = n
                pending["frames_required"] = needed
                warnings.append(pending)

        if not observable:
            confirmed = []

        return {
            "confirmed": confirmed,
            "warnings": warnings,
            "stable": len(warnings) == 0,
            "frame": self.frame,
        }
