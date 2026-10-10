"""FORMFIT Phase 4 - explainable coaching intelligence.
Additive layer: turns repeated form problems into concise coaching cues and a
session summary. It does not alter pose_engine thresholds or rep counting.
"""
import time
from collections import Counter, deque


class CoachingIntelligence:
    def __init__(self, history_size=80):
        self.history_size = max(20, int(history_size))
        self.reset()

    def reset(self):
        self.exercise = None
        self.frames = 0
        self.score_sum = 0.0
        self.status_counts = Counter()
        self.issue_counts = Counter()
        self.recent = deque(maxlen=self.history_size)
        self.last_coaching = None
        self.started_at = time.time()

    def start(self, exercise):
        self.reset()
        self.exercise = exercise

    def update(self, exercise, result, movement=None, quality=None, rep_quality=None):
        if exercise != self.exercise:
            self.start(exercise)

        self.frames += 1
        score = self._num(getattr(result, "score", 0), 0)
        status = str(getattr(result, "status", "")).lower()
        self.score_sum += score
        if status:
            self.status_counts[status] += 1

        issues = self._detect(exercise, result, movement or {}, quality or {})
        for issue in issues:
            self.issue_counts[issue["code"]] += 1

        primary = self._primary_issue(issues)
        cue = self._cue(exercise, primary)
        if cue:
            self.last_coaching = {
                "code": primary["code"],
                "title": primary["title"],
                "cue": cue,
                "severity": primary["severity"],
                "timestamp": int(time.time()),
            }

        self.recent.append({
            "score": score,
            "status": status,
            "issues": [x["code"] for x in issues],
        })

        return {
            "primary_issue": primary,
            "cue": cue,
            "issues": issues,
            "consistency": self._consistency(),
        }

    def _detect(self, exercise, result, movement, quality):
        found = []
        score = self._num(getattr(result, "score", 0), 0)
        status = str(getattr(result, "status", "")).lower()
        message = str(getattr(result, "message", ""))
        msg = message.lower()

        if quality.get("state") == "lost":
            found.append(self._issue("POSE_LOST", "Pose lost", "Move fully into camera view.", 4))
            return found

        if status == "red" or score < 45:
            found.append(self._issue("FORM_LOW", "Form needs attention", "Slow down and follow the highlighted correction.", 3))

        if status == "yellow" or score < 75:
            found.append(self._issue("FORM_WARNING", "Form warning", "Adjust the yellow target before the next rep.", 2))

        if movement.get("movement_quality") == "LOW_RANGE":
            found.append(self._issue("LOW_ROM", "Range is too small", "Use a controlled, comfortable full range.", 3))
        elif movement.get("movement_quality") == "TOO_FAST":
            found.append(self._issue("TOO_FAST", "Movement is too fast", "Slow the rep and control both directions.", 3))

        # Reuse explicit engine messages when they contain a useful cue.
        for token, code, title, cue in [
            ("knee", "KNEE_ALIGNMENT", "Check knee alignment", "Keep the knee tracking in line with the foot."),
            ("elbow", "ELBOW_ALIGNMENT", "Check elbow position", "Keep the elbow controlled instead of letting it drift."),
            ("back", "BACK_POSITION", "Check back position", "Keep your torso stable and avoid unnecessary leaning."),
            ("shoulder", "SHOULDER_POSITION", "Check shoulder position", "Keep the shoulder relaxed and controlled."),
        ]:
            if token in msg:
                found.append(self._issue(code, title, cue, 3))
                break

        return self._dedupe(found)

    def _primary_issue(self, issues):
        if not issues:
            return None
        ranked = sorted(issues, key=lambda x: (x["severity"], self.issue_counts[x["code"]]), reverse=True)
        return ranked[0]

    def _cue(self, exercise, primary):
        if not primary:
            return "Good control. Keep the same technique."
        return primary["cue"]

    def _consistency(self):
        if not self.recent:
            return 0
        good = sum(1 for x in self.recent if x["score"] >= 75 and x["status"] not in {"red"})
        return int(round(100 * good / len(self.recent)))

    def snapshot(self, reps=0, rep_quality=None):
        avg = round(self.score_sum / self.frames) if self.frames else None
        top = self.issue_counts.most_common(3)
        weakest = [
            {"code": code, "count": int(count)}
            for code, count in top
            if count > 0
        ]
        report = {
            "exercise": self.exercise,
            "frames": self.frames,
            "average_frame_score": avg,
            "consistency": self._consistency(),
            "top_issues": weakest,
            "last_coaching": self.last_coaching,
            "status_counts": dict(self.status_counts),
            "reps": int(reps),
            "duration_s": round(max(0.0, time.time() - self.started_at), 1),
        }
        if rep_quality:
            report["rep_quality"] = rep_quality
        report["summary"] = self._summary(avg, reps)
        return report

    def _summary(self, avg, reps):
        if not self.frames:
            return "Start moving to build your form report."
        if avg is not None and avg >= 85:
            return f"Strong session: {reps} reps recorded with consistent form."
        if avg is not None and avg >= 70:
            return f"Good session: {reps} reps recorded. Focus on the repeated correction cue."
        return f"Keep working: {reps} reps recorded. Slow down and fix the most frequent issue first."

    @staticmethod
    def _issue(code, title, cue, severity):
        return {"code": code, "title": title, "cue": cue, "severity": int(severity)}

    @staticmethod
    def _dedupe(items):
        seen = set()
        out = []
        for item in items:
            if item["code"] not in seen:
                seen.add(item["code"])
                out.append(item)
        return out

    @staticmethod
    def _num(value, fallback):
        try:
            value = float(value)
            return value if value == value else fallback
        except (TypeError, ValueError):
            return fallback
