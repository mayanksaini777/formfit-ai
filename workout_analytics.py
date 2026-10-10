"""FORMFIT Phase 6 - workout analytics.

Additive analytics layer. It consumes the existing rep/coaching/adaptive
outputs and never changes pose detection, exercise thresholds or rep counting.
"""
import time
from collections import deque


class WorkoutAnalytics:
    def __init__(self, max_reps=120, max_events=80):
        self.max_reps = max(20, int(max_reps))
        self.max_events = max(20, int(max_events))
        self.reset()

    def reset(self):
        self.exercise = None
        self.started_at = time.time()
        self.last_rep = 0
        self.rep_timeline = deque(maxlen=self.max_reps)
        self.events = deque(maxlen=self.max_events)
        self.score_sum = 0.0
        self.score_count = 0
        self.best_score = None
        self.worst_score = None
        self.last_quality_state = None

    def start(self, exercise):
        self.reset()
        self.exercise = exercise
        self._event("SESSION_STARTED", "Workout started", "Build consistent, controlled reps.", "info")

    def update(self, exercise, rep_quality=None, coaching=None, adaptive=None):
        if exercise != self.exercise:
            self.start(exercise)

        rep_quality = rep_quality or {}
        coaching = coaching or {}
        adaptive = adaptive or {}
        last = rep_quality.get("last_rep")
        if isinstance(last, dict):
            rep_no = self._int(last.get("rep"), 0)
            if rep_no > self.last_rep:
                item = {
                    "rep": rep_no,
                    "quality_score": self._int(last.get("quality_score"), 0),
                    "label": str(last.get("label") or "UNKNOWN"),
                    "form_score": self._int(last.get("form_score"), 0),
                    "rom_score": self._int(last.get("rom_score"), 0),
                    "tempo_score": self._int(last.get("tempo_score"), 0),
                    "rom": last.get("rom"),
                    "tempo_s": last.get("tempo_s"),
                    "warning_frames": self._int(last.get("warning_frames"), 0),
                    "timestamp": self._int(last.get("timestamp"), int(time.time())),
                }
                self.rep_timeline.append(item)
                self.last_rep = rep_no
                score = item["quality_score"]
                self.score_sum += score
                self.score_count += 1
                self.best_score = score if self.best_score is None else max(self.best_score, score)
                self.worst_score = score if self.worst_score is None else min(self.worst_score, score)
                self._rep_event(item)

        state = rep_quality.get("quality_state")
        if state and state != self.last_quality_state:
            self.last_quality_state = state
            if state in {"EXCELLENT", "GOOD"}:
                self._event("QUALITY_STATE", f"Form quality: {state}", "Keep the same controlled technique.", "success")
            elif state in {"NEEDS_WORK", "POOR"}:
                cue = coaching.get("cue") or adaptive.get("adaptive_cue") or "Follow the highlighted correction."
                self._event("QUALITY_STATE", f"Form quality: {state}", cue, "warning")

        return self.snapshot(rep_quality, coaching, adaptive)

    def _rep_event(self, item):
        score = item["quality_score"]
        if score >= 85:
            self._event("REP_GOOD", f"Rep {item['rep']} — strong", "Good control. Repeat this technique.", "success")
        elif score < 55:
            self._event("REP_LOW", f"Rep {item['rep']} — needs work", "Use the highlighted correction before the next rep.", "warning")

    def snapshot(self, rep_quality=None, coaching=None, adaptive=None):
        scores = [x["quality_score"] for x in self.rep_timeline]
        recent = scores[-5:]
        first = scores[:5]
        recent_avg = self._avg(recent)
        first_avg = self._avg(first)
        improvement = None if first_avg is None or recent_avg is None else round(recent_avg - first_avg, 1)
        return {
            "exercise": self.exercise,
            "duration_s": round(max(0.0, time.time() - self.started_at), 1),
            "reps": self.last_rep,
            "average_quality": self._avg(scores),
            "best_rep_score": self.best_score,
            "lowest_rep_score": self.worst_score,
            "recent_average": recent_avg,
            "improvement_vs_first_5": improvement,
            "trend": self._trend(scores),
            "timeline": list(self.rep_timeline),
            "events": list(self.events),
            "next_focus": self._next_focus(coaching, adaptive),
            "rep_quality": rep_quality or {},
            "coaching": coaching or {},
            "adaptive": adaptive or {},
        }

    def _next_focus(self, coaching, adaptive):
        if coaching and coaching.get("cue"):
            return coaching["cue"]
        if adaptive and adaptive.get("adaptive_cue"):
            return adaptive["adaptive_cue"]
        return "Keep a steady, controlled tempo and consistent range."

    @staticmethod
    def _trend(scores):
        if len(scores) < 3:
            return "STABLE"
        a = sum(scores[-3:-1]) / 2.0
        b = scores[-1]
        if b >= a + 5:
            return "UP"
        if b <= a - 5:
            return "DOWN"
        return "STABLE"

    @staticmethod
    def _avg(values):
        return None if not values else round(sum(values) / len(values))

    def _event(self, kind, title, message, severity):
        self.events.append({
            "type": kind,
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": int(time.time()),
        })

    @staticmethod
    def _int(value, fallback=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
