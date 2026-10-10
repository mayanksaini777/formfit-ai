"""Exercise-aware, segment-level pipe intelligence for FormFit.

This layer sits AFTER pose_engine/form_intelligence.  It never replaces their
scores or rep logic; it translates their exercise-specific mistakes into the
smallest anatomically relevant visual segments.
"""
from __future__ import annotations

import math

# MediaPipe landmark indices.
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_HEEL, R_HEEL = 29, 30
L_FOOT, R_FOOT = 31, 32

SEGMENTS = {
    "left_arm": [(L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST)],
    "right_arm": [(R_SHOULDER, R_ELBOW), (R_ELBOW, R_WRIST)],
    "left_leg": [(L_HIP, L_KNEE), (L_KNEE, L_ANKLE)],
    "right_leg": [(R_HIP, R_KNEE), (R_KNEE, R_ANKLE)],
    "left_torso": [(L_SHOULDER, L_HIP)],
    "right_torso": [(R_SHOULDER, R_HIP)],
    "left_full_arm": [(L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST)],
    "right_full_arm": [(R_SHOULDER, R_ELBOW), (R_ELBOW, R_WRIST)],
}

ARM_EXERCISES = {
    "bicep_curls", "hammer_curl", "tricep_extension", "front_raise",
    "lateral_shoulder_raises", "shoulder_press", "bench_press",
    "incline_dumbbell_press", "decline_bench_press", "incline_bench_press",
    "dumbbell_bench_press", "close_grip_bench_press", "chest_press_machine",
    "chest_fly", "cable_crossover", "low_cable_crossover",
    "lat_pulldown", "close_grip_lat_pulldown", "dumbbell_row",
}

LEG_EXERCISES = {
    "squat", "lunges", "reverse_lunge", "step_up", "calf_raise",
    "deadlift", "glute_bridge", "mountain_climber",
}

FLOOR_EXERCISES = {
    "push_up", "push_up_wide_grip", "push_up_diamond", "incline_push_up",
    "decline_push_up", "plank", "sit_up", "glute_bridge", "mountain_climber",
}

PUSHUP_FAMILY = {
    "push_up", "push_up_wide_grip", "push_up_diamond", "incline_push_up",
    "decline_push_up",
}


def _xy(lm, i):
    p = lm[i]
    return float(p.x), float(p.y)


def _vis(lm, i, threshold=0.35):
    try:
        return float(getattr(lm[i], "visibility", 1.0)) >= threshold
    except Exception:
        return False


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _angle(a, b, c):
    if a is None or b is None or c is None:
        return None
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    den = math.hypot(*ba) * math.hypot(*bc)
    if den <= 1e-8:
        return None
    cosv = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / den))
    return math.degrees(math.acos(cosv))


def _same_segment(a, b, ia, ib, lm, w, h, tol=24):
    try:
        x = (_xy(lm, ia)[0] * w, _xy(lm, ia)[1] * h)
        y = (_xy(lm, ib)[0] * w, _xy(lm, ib)[1] * h)
        direct = _dist(a, x) + _dist(b, y)
        reverse = _dist(a, y) + _dist(b, x)
        return min(direct, reverse) <= tol
    except Exception:
        return False


def _set_segments_red(result, lm, w, h, segment_pairs):
    changed = False
    updated = []
    for pipe in getattr(result, "pipes", []) or []:
        a, b, status = pipe[:3]
        extra = tuple(pipe[3:])
        red = any(_same_segment(a, b, ia, ib, lm, w, h) for ia, ib in segment_pairs)
        if red:
            status = "red"
            changed = True
        updated.append((a, b, status) + extra)
    result.pipes = updated
    return changed


def _red_side_from_issue(code):
    code = str(code or "").lower()
    if any(x in code for x in ("left", "_l", "left_")):
        return "left"
    if any(x in code for x in ("right", "_r", "right_")):
        return "right"
    return None


def _issue_segment_pairs(issues):
    pairs = set()
    for item in issues or []:
        code = str(item.get("code", "")).lower()
        side = _red_side_from_issue(code)
        if "knee" in code or "leg" in code:
            if side == "left":
                pairs.update(SEGMENTS["left_leg"])
            elif side == "right":
                pairs.update(SEGMENTS["right_leg"])
            else:
                pairs.update(SEGMENTS["left_leg"] + SEGMENTS["right_leg"])
        elif any(x in code for x in ("elbow", "arm", "wrist", "curl", "raise", "press_symmetry")):
            if side == "left":
                pairs.update(SEGMENTS["left_arm"])
            elif side == "right":
                pairs.update(SEGMENTS["right_arm"])
            else:
                pairs.update(SEGMENTS["left_arm"] + SEGMENTS["right_arm"])
        elif any(x in code for x in ("back", "torso", "body", "hip")):
            pairs.update(SEGMENTS["left_torso"] + SEGMENTS["right_torso"])
    return pairs


def _pushup_position_ok(lm):
    visible_ids = [L_SHOULDER, L_HIP, L_ANKLE]
    if not all(_vis(lm, i) for i in visible_ids):
        return None
    s, h, a = _xy(lm, L_SHOULDER), _xy(lm, L_HIP), _xy(lm, L_ANKLE)
    torso_dx = abs(h[0] - s[0])
    torso_dy = abs(h[1] - s[1])
    torso_len = max(math.hypot(h[0] - s[0], h[1] - s[1]), 1e-6)
    # A real push-up is predominantly horizontal.  This gate is deliberately
    # conservative so a normal side-view setup isn't rejected accidentally.
    horizontal_torso = torso_dy / torso_len < 0.68
    body_span = _dist(s, a)
    return horizontal_torso and body_span > 0.25


def _floor_position_ok(exercise, lm):
    if exercise in PUSHUP_FAMILY:
        return _pushup_position_ok(lm)
    if exercise == "plank":
        return _pushup_position_ok(lm)
    if exercise in {"sit_up", "glute_bridge"}:
        if not all(_vis(lm, i) for i in (L_SHOULDER, L_HIP, L_KNEE)):
            return None
        s, h, k = _xy(lm, L_SHOULDER), _xy(lm, L_HIP), _xy(lm, L_KNEE)
        # Shoulder and hip should not be vertically stacked like standing.
        return abs(h[1] - s[1]) / max(_dist(s, h), 1e-6) < 0.82
    return True


def _exercise_position_gate(exercise, lm):
    """Return (scope, message) for genuinely global exercise-position errors."""
    if exercise in FLOOR_EXERCISES:
        ok = _floor_position_ok(exercise, lm)
        if ok is False:
            return "full", {
                "push_up": "GET INTO PUSH-UP POSITION",
                "push_up_wide_grip": "GET INTO WIDE-GRIP PUSH-UP POSITION",
                "push_up_diamond": "GET INTO DIAMOND PUSH-UP POSITION",
                "incline_push_up": "GET INTO INCLINE PUSH-UP POSITION",
                "decline_push_up": "GET INTO DECLINE PUSH-UP POSITION",
                "plank": "GET INTO PLANK POSITION",
                "sit_up": "GET INTO SIT-UP POSITION",
                "glute_bridge": "LIE DOWN FOR GLUTE BRIDGE",
            }.get(exercise, "GET INTO THE CORRECT EXERCISE POSITION")
    return "segment", None


def apply(result, exercise, landmarks, width, height):
    """Apply exercise-aware pipe scope. Returns (scope, focus_codes)."""
    scope, message = _exercise_position_gate(exercise, landmarks)
    if scope == "full":
        result.status = "red"
        result.message = message
        result.score = 0
        result.good_rep = False
        result.pipes = [(a, b, "red") + tuple(p[3:]) for p in (result.pipes or [])]
        return "full", ["exercise_position"]

    # Translate explainable issue codes into the smallest body region.
    pairs = _issue_segment_pairs(getattr(result, "issues", []))

    # Explicit result targets are also useful when an exercise-specific rule
    # exists but its issue code is generic.
    for target in getattr(result, "targets", []) or []:
        label = str(target[2] if len(target) > 2 else "").lower()
        if "left elbow" in label or "left arm" in label:
            pairs.update(SEGMENTS["left_arm"])
        elif "right elbow" in label or "right arm" in label:
            pairs.update(SEGMENTS["right_arm"])
        elif "left knee" in label or "left leg" in label:
            pairs.update(SEGMENTS["left_leg"])
        elif "right knee" in label or "right leg" in label:
            pairs.update(SEGMENTS["right_leg"])

    changed = _set_segments_red(result, landmarks, width, height, pairs) if pairs else False

    # A global failure from the engine is global only when it is truly a
    # visibility/exercise-position failure. Otherwise preserve local pipes.
    if str(getattr(result, "status", "")).lower() == "red" and not changed:
        msg = str(getattr(result, "message", "")).lower()
        global_words = ("show your full body", "not detected", "move back", "too close", "too far")
        if any(word in msg for word in global_words):
            result.pipes = [(a, b, "red") + tuple(p[3:]) for p in (result.pipes or [])]
            return "full", ["global_visibility"]

    focus = sorted({str(x) for x in getattr(result, "issues", []) and [i.get("code") for i in result.issues] if x})
    return "segment", focus
