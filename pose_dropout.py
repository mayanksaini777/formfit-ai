"""Transient MediaPipe pose-dropout recovery for live video.

A missed pose frame is a tracking event, not a form error. Keep the last
known skeleton for a few frames so the UI does not blink or stick red.
"""
from __future__ import annotations

from copy import copy


class PoseDropoutRecovery:
    def __init__(self, max_hold_frames=6):
        self.max_hold_frames = max(1, int(max_hold_frames))
        self.reset()

    def reset(self):
        self.last_landmarks = None
        self.missed_frames = 0

    def valid(self, landmarks):
        if landmarks is None:
            return self.missing()
        self.last_landmarks = [copy(x) for x in landmarks]
        self.missed_frames = 0
        return landmarks

    def missing(self):
        self.missed_frames += 1
        if self.last_landmarks is not None and self.missed_frames <= self.max_hold_frames:
            return [copy(x) for x in self.last_landmarks]
        return None
