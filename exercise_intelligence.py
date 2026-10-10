"""Exercise-specific validation and rep gating for FormFit.

This is an additive layer in front of the existing pose_engine.RepCounter.
It answers two separate questions:
  1) Is the selected exercise actually being performed from a compatible pose?
  2) Which anatomical region is currently failing?

It deliberately does not replace pose_engine.py. The existing engine remains the
source of landmarks/angles and the final rep counter; this layer gates bad frames
so a random elbow angle cannot become a repetition.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import exercise_knowledge as knowledge

L_SH, R_SH = 11, 12
L_EL, R_EL = 13, 14
L_WR, R_WR = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANK, R_ANK = 27, 28

ARM_FAMILY = {
    "bicep_curls", "hammer_curl", "tricep_extension", "front_raise",
    "lateral_shoulder_raises", "shoulder_press", "bench_press",
    "incline_dumbbell_press", "decline_bench_press", "incline_bench_press",
    "dumbbell_bench_press", "close_grip_bench_press", "chest_press_machine",
    "chest_fly", "cable_crossover", "low_cable_crossover", "lat_pulldown",
    "close_grip_lat_pulldown", "dumbbell_row",
}
LEG_FAMILY = {
    "squat", "lunges", "reverse_lunge", "step_up", "calf_raise", "deadlift",
}
FLOOR_FAMILY = {
    "push_up", "push_up_wide_grip", "push_up_diamond", "incline_push_up",
    "decline_push_up", "plank", "sit_up", "glute_bridge", "mountain_climber",
    "burpee",
}

@dataclass
class Validation:
    compatible: bool = True
    rep_ready: bool = True
    scope: str = "segment"  # segment | full
    score_cap: int | None = None
    issues: list[dict] = field(default_factory=list)
    focus: list[str] = field(default_factory=list)

class ExerciseIntelligence:
    def __init__(self):
        self.exercise = None
        self.prev = {}
        self.valid_streak = 0
        self.invalid_streak = 0
        self.last_signal = None
        self.last_rep_signature = None

    def reset(self, exercise):
        self.exercise = exercise
        self.prev.clear()
        self.valid_streak = 0
        self.invalid_streak = 0
        self.last_signal = None
        self.last_rep_signature = None

    @staticmethod
    def _xy(lm, i):
        try: return float(lm[i].x), float(lm[i].y)
        except Exception: return None

    @staticmethod
    def _vis(lm, i, t=.42):
        try: return float(getattr(lm[i], "visibility", 0.0)) >= t
        except Exception: return False

    @classmethod
    def _angle(cls, lm, a, b, c):
        p1, p2, p3 = cls._xy(lm,a), cls._xy(lm,b), cls._xy(lm,c)
        if not all((p1,p2,p3)): return None
        v1=(p1[0]-p2[0],p1[1]-p2[1]); v2=(p3[0]-p2[0],p3[1]-p2[1])
        d=math.hypot(*v1)*math.hypot(*v2)
        if d < 1e-8: return None
        c=max(-1,min(1,(v1[0]*v2[0]+v1[1]*v2[1])/d))
        return math.degrees(math.acos(c))

    @classmethod
    def _dist(cls,lm,a,b):
        p,q=cls._xy(lm,a),cls._xy(lm,b)
        return math.hypot(p[0]-q[0],p[1]-q[1]) if p and q else None

    @classmethod
    def _lean(cls,lm,s,h):
        p,q=cls._xy(lm,s),cls._xy(lm,h)
        if not p or not q: return None
        dx=abs(p[0]-q[0]); dy=abs(p[1]-q[1])
        return math.degrees(math.atan2(dx,max(dy,1e-6)))

    @staticmethod
    def _issue(code,title,detail,priority="medium",recommendation=""):
        return {"code":code,"title":title,"detail":detail,"priority":priority,"recommendation":recommendation}

    def _arm(self,lm,side):
        if side == "left": s,e,w=L_SH,L_EL,L_WR
        else: s,e,w=R_SH,R_EL,R_WR
        if not all(self._vis(lm,i) for i in (s,e,w)): return None
        elbow=self._angle(lm,s,e,w)
        sw=self._dist(lm,s,e)
        torso=self._dist(lm,s,L_HIP if side=="left" else R_HIP)
        if elbow is None or sw is None or torso is None: return None
        ep=self._xy(lm,e); sp=self._xy(lm,s); hp=self._xy(lm,L_HIP if side=="left" else R_HIP)
        drift=abs(ep[0]-sp[0])/max(torso,.05)
        return {"side":side,"elbow":elbow,"drift":drift,"s":sp,"e":ep,"h":hp}

    def _biceps(self,lm,exercise):
        out=Validation(); arms=[a for a in (self._arm(lm,"left"),self._arm(lm,"right")) if a]
        if not arms:
            out.rep_ready=False; out.score_cap=25; return out
        valid=[]
        for a in arms:
            # Upper arm should remain reasonably near torso. This catches the
            # user's video case where both arms were held sideways and the raw
            # elbow angle accidentally generated reps.
            if a["drift"] > .55:
                out.issues.append(self._issue(
                    f"curl_elbow_{a['side']}","KEEP ELBOW CLOSE",
                    f"{a['side'].title()} upper arm is drifting away from the torso.","high",
                    "Keep the upper arm close and curl from the elbow."
                ))
            else:
                valid.append(a)
            if a["elbow"] < 35:
                out.issues.append(self._issue(
                    f"curl_overflex_{a['side']}","DON'T OVER-CURL",
                    f"{a['side'].title()} elbow is excessively closed.","medium",
                    "Stop before forcing the forearm against the upper arm."
                ))
        # At least one arm must have a plausible curl posture to allow the
        # existing counter to progress. Arms-out poses are therefore blocked.
        out.rep_ready=bool(valid)
        if not valid:
            out.compatible=False; out.score_cap=0
            out.scope="full"  # both sides violate the exercise setup
        elif any(i["priority"]=="high" for i in out.issues):
            out.score_cap=58
        return out

    def _pushup(self,lm,exercise):
        out=Validation()
        ids=(L_SH,L_HIP,L_ANK)
        if not all(self._vis(lm,i) for i in ids): out.rep_ready=False; return out
        s,h,a=(self._xy(lm,i) for i in ids)
        torso_len=max(math.hypot(h[0]-s[0],h[1]-s[1]),1e-6)
        horizontal=abs(h[1]-s[1])/torso_len < .70
        span=math.hypot(a[0]-s[0],a[1]-s[1])
        if not horizontal or span < .25:
            out.compatible=False; out.rep_ready=False; out.scope="full"; out.score_cap=0
            out.issues.append(self._issue("exercise_position","GET INTO POSITION",
                "The selected push-up requires a floor/horizontal body position.","high",
                "Get into the push-up position before starting the set."))
            return out
        # Body-line error is local to torso/hips, not the whole skeleton.
        angle=self._angle(lm,L_SH,L_HIP,L_ANK)
        if angle is not None and angle < 150:
            out.issues.append(self._issue("pushup_body","KEEP BODY STRAIGHT",
                "Hips are dropping or lifting out of line.","high",
                "Brace the core and keep shoulders, hips and ankles aligned."))
            out.score_cap=55
        return out

    def _squat_like(self,lm,exercise):
        out=Validation(); knees=[]
        for side,h,k,a in (("left",L_HIP,L_KNEE,L_ANK),("right",R_HIP,R_KNEE,R_ANK)):
            if all(self._vis(lm,i) for i in (h,k,a)):
                ang=self._angle(lm,h,k,a)
                if ang is not None:
                    knees.append((side,ang))
                    # Excessive inward/outward knee deviation relative to ankle.
                    kp,ap=self._xy(lm,k),self._xy(lm,a)
                    if abs(kp[0]-ap[0]) > .14:
                        out.issues.append(self._issue(f"knee_align_{side}","KNEE ALIGNMENT",
                            f"{side.title()} knee is drifting away from the foot.","high",
                            "Track the knee in the same direction as the toes."))
        if not knees: out.rep_ready=False
        # Standing is a valid start position; only gross torso collapse is blocked.
        for side,s,h in (("left",L_SH,L_HIP),("right",R_SH,R_HIP)):
            lean=self._lean(lm,s,h)
            if lean is not None and lean > 55:
                out.issues.append(self._issue(f"squat_back_{side}","CONTROL YOUR BACK",
                    "Torso is excessively folded for a safe squat pattern.","high",
                    "Brace your core and keep your chest controlled."))
        if any(i["priority"]=="high" for i in out.issues): out.score_cap=55
        return out

    def _lunge(self,lm,exercise):
        return self._squat_like(lm,exercise)

    def _press(self,lm,exercise):
        out=Validation(); arms=[a for a in (self._arm(lm,"left"),self._arm(lm,"right")) if a]
        if not arms: out.rep_ready=False; return out
        for a in arms:
            if a["drift"]>.72:
                out.issues.append(self._issue(f"press_arm_{a['side']}","CONTROL ELBOW",
                    f"{a['side'].title()} arm is drifting away from the press path.","medium",
                    "Keep the elbow under the hand and press in control."))
        lean=max([x for x in (self._lean(lm,L_SH,L_HIP),self._lean(lm,R_SH,R_HIP)) if x is not None] or [0])
        if exercise=="shoulder_press" and lean>28:
            out.issues.append(self._issue("press_back","DO NOT LEAN BACK",
                "Torso is leaning excessively during the press.","high",
                "Brace your core and keep ribs stacked over the hips."))
        if any(i["priority"]=="high" for i in out.issues): out.score_cap=55
        return out

    def _row(self,lm,exercise):
        out=Validation(); lean=max([x for x in (self._lean(lm,L_SH,L_HIP),self._lean(lm,R_SH,R_HIP)) if x is not None] or [0])
        if lean < 18:
            out.issues.append(self._issue("row_back","SET YOUR BACK ANGLE",
                "Torso is too upright for the selected row pattern.","high",
                "Hinge at the hips and keep a neutral spine.")); out.score_cap=55
        out.rep_ready=all(self._vis(lm,i) for i in (L_SH,L_HIP,L_EL,L_WR))
        return out

    def _floor_generic(self,lm,exercise):
        # Generic floor requirement for exercises that should not be mistaken
        # for a standing movement. Mountain climber/burpee are dynamic and are
        # handled more permissively than push-up/plank.
        if exercise in {"mountain_climber","burpee"}: return Validation()
        return self._pushup(lm,exercise) if exercise in {"plank","sit_up","glute_bridge"} else Validation()

    def _knowledge_checks(self, exercise, lm, validation):
        """Apply conservative, data-driven biomechanics checks.

        These checks never invent a fault when the required landmarks are not
        observable. They only add an error when the profile explicitly says
        the condition is measurable from the current camera view.
        """
        profile = knowledge.get(exercise)
        if not profile:
            return validation

        def vis(*ids):
            return all(self._vis(lm, i) for i in ids)

        def add(code, title, detail, priority="high", recommendation=""):
            if not any(i.get("code") == code for i in validation.issues):
                validation.issues.append(self._issue(code, title, detail, priority, recommendation))

        invalid = profile.get("invalid", {})
        if profile.get("family") in {"curl", "arm_extension", "vertical_press", "lateral_raise", "front_raise", "horizontal_press", "horizontal_fly", "vertical_pull"}:
            for side, sh, el, wr, hip in (("left", L_SH, L_EL, L_WR, L_HIP), ("right", R_SH, R_EL, R_WR, R_HIP)):
                if not vis(sh, el, wr):
                    continue
                sy = self._xy(lm, sh)[1]; ey = self._xy(lm, el)[1]; wy = self._xy(lm, wr)[1]
                torso = max(self._dist(lm, sh, hip) or 0.05, 0.05)
                if "elbow_above_shoulder" in invalid and ey < sy - float(invalid["elbow_above_shoulder"]) * torso:
                    add(f"knowledge_elbow_above_{side}", "ELBOW TOO HIGH", f"{side.title()} elbow is above the shoulder for this exercise.", "high", "Keep the elbow below the required shoulder line.")
                if "wrist_above_shoulder" in invalid and wy < sy - float(invalid["wrist_above_shoulder"]) * torso:
                    add(f"knowledge_wrist_above_{side}", "HAND TOO HIGH", f"{side.title()} hand is above the allowed shoulder line.", "high", "Lower the hand and keep the movement in the exercise path.")
                if "wrist_above_head" in invalid and wy < min(self._xy(lm, 0)[1], sy) - float(invalid["wrist_above_head"]) * torso:
                    add(f"knowledge_wrist_overhead_{side}", "ARM TOO HIGH", f"{side.title()} arm is higher than the exercise allows.", "high", "Stop at the prescribed range instead of lifting overhead.")
                if "elbow_drift_ratio" in invalid:
                    ep, sp = self._xy(lm, el), self._xy(lm, sh)
                    drift = abs(ep[0] - sp[0]) / torso
                    if drift > float(invalid["elbow_drift_ratio"]):
                        add(f"knowledge_elbow_drift_{side}", "ELBOW DRIFT", f"{side.title()} elbow is drifting away from the torso.", "high", "Keep the upper arm controlled and close to the intended path.")

        lean_limit = invalid.get("torso_lean_deg")
        if lean_limit is not None:
            leans = []
            for sh, hip in ((L_SH, L_HIP), (R_SH, R_HIP)):
                x = self._lean(lm, sh, hip)
                if x is not None: leans.append(x)
            if leans and max(leans) > float(lean_limit):
                add("knowledge_torso_lean", "CONTROL YOUR TORSO", "Torso lean exceeds the exercise's safe observable range.", "high", "Brace your core and keep the torso controlled.")

        if "knee_drift_px_ratio" in invalid:
            for side, hip, knee, ankle in (("left", L_HIP, L_KNEE, L_ANK), ("right", R_HIP, R_KNEE, R_ANK)):
                if vis(hip, knee, ankle):
                    kp, ap = self._xy(lm, knee), self._xy(lm, ankle)
                    if abs(kp[0] - ap[0]) > float(invalid["knee_drift_px_ratio"]):
                        add(f"knowledge_knee_drift_{side}", "KNEE TRACKING", f"{side.title()} knee is not tracking over the foot.", "high", "Track the knee in line with the foot.")

        if "body_line_min_deg" in invalid and vis(L_SH, L_HIP, L_ANK):
            angle = self._angle(lm, L_SH, L_HIP, L_ANK)
            if angle is not None and angle < float(invalid["body_line_min_deg"]):
                add("knowledge_body_line", "KEEP BODY STRAIGHT", "Shoulders, hips and ankles are not maintaining the required body line.", "high", "Brace the core and keep the body in one controlled line.")

        # Any newly discovered high-priority fault blocks rep progression.
        if any(i.get("priority") == "high" for i in validation.issues):
            validation.rep_ready = False
        return validation

    def validate(self,exercise,lm,result=None):
        if exercise != self.exercise: self.reset(exercise)
        if exercise in {"bicep_curls","hammer_curl"}: v=self._biceps(lm,exercise)
        elif exercise in {"push_up","push_up_wide_grip","push_up_diamond","incline_push_up","decline_push_up"}: v=self._pushup(lm,exercise)
        elif exercise in {"squat","deadlift","step_up","calf_raise"}: v=self._squat_like(lm,exercise)
        elif exercise in {"lunges","reverse_lunge"}: v=self._lunge(lm,exercise)
        elif exercise in {"shoulder_press","lateral_shoulder_raises","tricep_extension","front_raise","bench_press","incline_dumbbell_press","decline_bench_press","incline_bench_press","dumbbell_bench_press","close_grip_bench_press","chest_press_machine","chest_fly","cable_crossover","low_cable_crossover","lat_pulldown","close_grip_lat_pulldown"}: v=self._press(lm,exercise)
        elif exercise=="dumbbell_row": v=self._row(lm,exercise)
        elif exercise in FLOOR_FAMILY: v=self._floor_generic(lm,exercise)
        else: v=Validation()

        # Apply the exercise's explicit knowledge profile after the family
        # validator. This is intentionally conservative: unknown biomechanics
        # are not guessed from a single RGB camera.
        v = self._knowledge_checks(exercise, lm, v)

        # Require two consecutive compatible frames before allowing the core
        # counter to progress. This removes one-frame angle spikes.
        if v.rep_ready:
            self.valid_streak=min(self.valid_streak+1,6); self.invalid_streak=0
        else:
            self.invalid_streak=min(self.invalid_streak+1,6); self.valid_streak=0
        v.rep_ready = v.rep_ready and self.valid_streak >= 2
        return v
