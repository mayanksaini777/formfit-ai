"""FORMFIT Phase 3 - repetition quality intelligence.
Additive layer over the existing RepCounter. It never changes the counter's
core thresholds; it scores each completed repetition using movement quality,
range of motion, tempo and form score.
"""
import time
from collections import deque


class RepQualityTracker:
    def __init__(self, history_size=30):
        self.history_size = max(5, int(history_size))
        self.reset()

    def reset(self):
        self.exercise = None
        self.rep_at_start = 0
        self.active_min_score = 101
        self.active_scores = []
        self.active_rom = []
        self.active_tempo = []
        self.active_bad_frames = 0
        self.last_completed = None
        self.history = deque(maxlen=self.history_size)
        self.session_total_score = 0.0

    def start(self, exercise, reps=0):
        self.reset()
        self.exercise = exercise
        self.rep_at_start = int(reps)

    def update(self, exercise, result, movement, reps):
        if exercise != self.exercise:
            self.start(exercise, reps)

        score = self._number(getattr(result, "score", 0), 0)
        self.active_min_score = min(self.active_min_score, score)
        self.active_scores.append(score)

        rom = self._number((movement or {}).get("rom"), None)
        tempo = self._number((movement or {}).get("tempo_s"), None)
        if rom is not None:
            self.active_rom.append(rom)
        if tempo is not None:
            self.active_tempo.append(tempo)

        if str(getattr(result, "status", "")).lower() in {"yellow", "red"}:
            self.active_bad_frames += 1

        completed = int(reps) > int(self.rep_at_start)
        if completed:
            completed_count = int(reps) - int(self.rep_at_start)
            # Handle an unexpected jump safely; one quality record per new rep.
            for _ in range(max(1, completed_count)):
                rep = self._finish_rep(exercise)
                self.history.append(rep)
                self.last_completed = rep
                self.session_total_score += rep["quality_score"]
            self.rep_at_start = int(reps)
            self.active_min_score = 101
            self.active_scores = []
            self.active_rom = []
            self.active_tempo = []
            self.active_bad_frames = 0

        return self.snapshot(reps)

    def _finish_rep(self, exercise):
        avg_score = sum(self.active_scores) / len(self.active_scores) if self.active_scores else 0
        min_score = 0 if self.active_min_score == 101 else self.active_min_score
        rom = max(self.active_rom) if self.active_rom else 0.0
        avg_tempo = sum(self.active_tempo) / len(self.active_tempo) if self.active_tempo else None

        rom_score = self._rom_score(exercise, rom)
        tempo_score = self._tempo_score(avg_tempo)
        form_score = max(0.0, min(100.0, avg_score * 0.65 + min_score * 0.35))
        quality = round(form_score * 0.65 + rom_score * 0.20 + tempo_score * 0.15)
        quality = int(max(0, min(100, quality)))

        if quality >= 85:
            label = "EXCELLENT"
        elif quality >= 70:
            label = "GOOD"
        elif quality >= 55:
            label = "NEEDS WORK"
        else:
            label = "POOR"

        return {
            "rep": len(self.history) + 1,
            "quality_score": quality,
            "label": label,
            "form_score": int(round(form_score)),
            "rom_score": int(round(rom_score)),
            "tempo_score": int(round(tempo_score)),
            "rom": round(rom, 1),
            "tempo_s": None if avg_tempo is None else round(avg_tempo, 2),
            "warning_frames": int(self.active_bad_frames),
            "exercise": exercise,
            "timestamp": int(time.time()),
        }

    def _rom_score(self, exercise, rom):
        targets = {
            "squat": (30, 70),
            "lunges": (30, 70),
            "push_up": (35, 85),
            "bicep_curls": (45, 90),
            "tricep_extension": (35, 90),
            "shoulder_press": (45, 100),
            "lateral_shoulder_raises": (35, 85),
        }
        low, ideal = targets.get(exercise, (25, 75))
        if rom >= ideal:
            return 100.0
        if rom <= low:
            return 45.0
        return 45.0 + 55.0 * (rom - low) / max(ideal - low, 1)

    def _tempo_score(self, tempo):
        if tempo is None:
            return 70.0
        if tempo < 0.22:
            return 35.0
        if tempo < 0.40:
            return 65.0
        if tempo <= 1.80:
            return 100.0
        if tempo <= 3.0:
            return 80.0
        return 60.0

    def snapshot(self, reps):
        avg = round(self.session_total_score / len(self.history)) if self.history else None
        return {
            "completed_reps": int(reps),
            "last_rep": self.last_completed,
            "history": list(self.history),
            "average_quality": avg,
            "quality_state": self._state(),
        }

    def _state(self):
        if not self.history:
            return "WAITING"
        avg = self.session_total_score / len(self.history)
        if avg >= 85:
            return "EXCELLENT"
        if avg >= 70:
            return "GOOD"
        if avg >= 55:
            return "NEEDS_WORK"
        return "POOR"

    @staticmethod
    def _number(value, fallback):
        try:
            value = float(value)
            return value if value == value else fallback
        except (TypeError, ValueError):
            return fallback
