
"""FORMFIT Exercise Form Knowledge V3.

Camera-coaching knowledge layer for the 10 exercises currently supported by
the project. It is intentionally additive: it returns issue/recommendation
metadata and yellow target positions without changing the core pose engine,
rep counter, pipes, or exercise dispatch.

The thresholds are conservative camera heuristics, not medical standards.
"""
import math
import pose_engine as e

FORM_KNOWLEDGE = {
    "squat": {
        "setup": ["stable feet", "neutral spine", "chest up", "knees track with toes"],
        "checks": ["torso lean", "knee tracking", "depth", "symmetry"],
    },
    "lunges": {
        "setup": ["tall torso", "stable front foot", "hips controlled"],
        "checks": ["torso lean", "front-knee tracking", "depth", "symmetry"],
    },
    "bicep_curls": {
        "setup": ["upper arms close", "wrists controlled", "torso still"],
        "checks": ["elbow drift", "symmetry", "swing", "range"],
    },
    "lateral_shoulder_raises": {
        "setup": ["soft elbows", "torso still", "shoulders relaxed"],
        "checks": ["shoulder-height range", "symmetry", "torso lean"],
    },
    "shoulder_press": {
        "setup": ["core braced", "torso upright", "hands even"],
        "checks": ["back lean", "hand symmetry", "overhead path"],
    },
    "tricep_extension": {
        "setup": ["elbows stable", "upper arms controlled", "torso neutral"],
        "checks": ["elbow drift", "torso lean", "symmetry"],
    },
    "push_up": {
        "setup": ["hands stable", "core braced", "head-to-heel line"],
        "checks": ["body line", "elbow path", "depth", "symmetry"],
    },
    "dumbbell_row": {
        "setup": ["hip hinge", "neutral spine", "shoulders controlled"],
        "checks": ["torso angle", "elbow path", "shoulder symmetry"],
    },
    "sit_up": {
        "setup": ["feet stable", "neck neutral", "controlled trunk"],
        "checks": ["trunk motion", "symmetry", "momentum"],
    },
    "lat_pulldown": {
        "setup": ["stable seat", "torso controlled", "shoulders down"],
        "checks": ["torso lean", "elbow path", "symmetry", "controlled return"],
    },
    "close_grip_lat_pulldown": {
        "setup": ["stable seat", "torso controlled", "elbows even"],
        "checks": ["torso lean", "elbow path", "symmetry", "controlled return"],
    },
    "jumping_jack": {
        "setup": ["upright torso", "soft landing", "balanced stance"],
        "checks": ["arm symmetry", "leg symmetry", "open position"],
    },
}


def _p(lm, idx, w, h, threshold=0.60):
    try:
        if not e.visible(lm, idx, threshold):
            return None
        return e.xy(lm, idx, w, h)
    except Exception:
        return None


def _angle(a, b, c):
    if a is None or b is None or c is None:
        return None
    return e.angle(a, b, c)


def _lean(a, b):
    if a is None or b is None:
        return None
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    if abs(dy) < 1:
        return 90.0
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def _add_issue(result, code, title, detail, priority, recommendation):
    if not any(x.get("code") == code for x in result.issues):
        result.issues.append({
            "code": code,
            "title": title,
            "detail": detail,
            "priority": priority,
            "recommendation": recommendation,
        })
    if recommendation and recommendation not in result.recommendations:
        result.recommendations.append(recommendation)


def _guide(result, actual, desired, label):
    if actual is None or desired is None:
        return
    if not all(math.isfinite(float(v)) for v in (*actual, *desired)):
        return
    if e.distance(actual, desired) < 7:
        return
    if any(len(t) >= 3 and t[2] == label for t in result.targets):
        return
    result.targets.append((actual, desired, label))


def _side(lm, w, h):
    choices = []
    for name, s, hip, knee, ankle in (
        ("LEFT", e.LEFT_SHOULDER, e.LEFT_HIP, e.LEFT_KNEE, e.LEFT_ANKLE),
        ("RIGHT", e.RIGHT_SHOULDER, e.RIGHT_HIP, e.RIGHT_KNEE, e.RIGHT_ANKLE),
    ):
        ids = (s, hip, knee, ankle)
        if all(_p(lm, i, w, h) is not None for i in ids):
            score = sum(float(getattr(lm[i], "visibility", 0)) for i in ids)
            choices.append((score, name, s, hip, knee, ankle))
    return max(choices, key=lambda x: x[0]) if choices else None


def _torso(lm, side, w, h):
    s = e.LEFT_SHOULDER if side == "LEFT" else e.RIGHT_SHOULDER
    hip = e.LEFT_HIP if side == "LEFT" else e.RIGHT_HIP
    sp, hp = _p(lm, s, w, h), _p(lm, hip, w, h)
    return _lean(sp, hp), sp, hp


def _project(point, a, b):
    if not point or not a or not b:
        return None
    vx, vy = b[0] - a[0], b[1] - a[1]
    den = vx * vx + vy * vy
    if den < 1e-6:
        return None
    t = ((point[0] - a[0]) * vx + (point[1] - a[1]) * vy) / den
    return (a[0] + t * vx, a[1] + t * vy)


def apply_knowledge(result, exercise, lm, w, h):
    """Apply exercise-specific form knowledge and yellow correction targets."""
    if exercise not in FORM_KNOWLEDGE:
        return result

    # SQUAT
    if exercise == "squat":
        best = _side(lm, w, h)
        if best:
            _, side, sid, hid, kid, aid = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            knee, ankle = _p(lm, kid, w, h), _p(lm, aid, w, h)
            if lean is not None and lean > 30:
                _add_issue(result, "knowledge_squat_back", "BACK LEAN TOO MUCH",
                            "Torso is leaning too far forward.", "high",
                            "Bring your chest up and brace your core.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "CHEST UP")
            elif lean is not None and lean > 23:
                _add_issue(result, "knowledge_squat_back_soft", "KEEP CHEST UP",
                            "Torso lean is above the coaching target.", "medium",
                            "Lift your chest slightly and brace your core.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "CHEST UP")
            if knee and ankle and shoulder and hip:
                scale = max(e.distance(shoulder, hip), 1)
                if abs(knee[0] - ankle[0]) / scale > 0.38:
                    _add_issue(result, "knowledge_squat_knee", "KNEE ALIGNMENT",
                                "Knee is drifting away from the foot line.", "high",
                                "Keep the knee tracking in the same direction as the toes.")
                    _guide(result, knee, (ankle[0], knee[1]), "KNEE ALIGN")

    # LUNGE
    elif exercise == "lunges":
        best = _side(lm, w, h)
        if best:
            _, side, sid, hid, kid, aid = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            knee, ankle = _p(lm, kid, w, h), _p(lm, aid, w, h)
            if lean is not None and lean > 30:
                _add_issue(result, "knowledge_lunge_torso", "KEEP TORSO UPRIGHT",
                            "Torso is leaning too far forward.", "high",
                            "Brace your core and keep the chest tall.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "CHEST UP")
            if knee and ankle and shoulder and hip:
                if abs(knee[0] - ankle[0]) / max(e.distance(shoulder, hip), 1) > 0.42:
                    _add_issue(result, "knowledge_lunge_knee", "FRONT KNEE ALIGNMENT",
                                "Front knee is drifting from the foot line.", "high",
                                "Keep the front knee tracking with the toes.")
                    _guide(result, knee, (ankle[0], knee[1]), "KNEE ALIGN")

    # BICEP CURL
    elif exercise == "bicep_curls":
        for side, sid, eid in (
            ("LEFT", e.LEFT_SHOULDER, e.LEFT_ELBOW),
            ("RIGHT", e.RIGHT_SHOULDER, e.RIGHT_ELBOW),
        ):
            shoulder = _p(lm, sid, w, h)
            elbow = _p(lm, eid, w, h)
            hip = _p(lm, e.LEFT_HIP if side == "LEFT" else e.RIGHT_HIP, w, h)
            if shoulder and elbow and hip:
                if abs(elbow[0] - shoulder[0]) / max(e.distance(shoulder, hip), 1) > 0.52:
                    _add_issue(result, "knowledge_curl_elbow_" + side.lower(),
                                "KEEP ELBOW FIXED",
                                f"{side.title()} elbow is drifting away from the torso.",
                                "high", "Keep the upper arm close to your body.")
                    _guide(result, elbow, (shoulder[0], elbow[1]), "ELBOW BACK")
        best = _side(lm, w, h)
        if best:
            _, side, *_ = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            if lean is not None and lean > 25:
                _add_issue(result, "knowledge_curl_torso", "KEEP TORSO STILL",
                            "Torso is moving to assist the curl.", "medium",
                            "Stand tall and avoid swinging your body.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "TORSO HERE")

    # LATERAL RAISE
    elif exercise == "lateral_shoulder_raises":
        pairs = []
        for side, sid, wid in (
            ("LEFT", e.LEFT_SHOULDER, e.LEFT_WRIST),
            ("RIGHT", e.RIGHT_SHOULDER, e.RIGHT_WRIST),
        ):
            shoulder, wrist = _p(lm, sid, w, h), _p(lm, wid, w, h)
            if shoulder and wrist:
                pairs.append((side, shoulder, wrist))
                if shoulder[1] - wrist[1] > 0.12 * h:
                    _add_issue(result, "knowledge_lateral_high_" + side.lower(),
                                "ARM TOO HIGH", f"{side.title()} arm is above shoulder height.",
                                "medium", "Stop around shoulder height.")
                    _guide(result, wrist, (wrist[0], shoulder[1]), "SHOULDER HEIGHT")
        if len(pairs) == 2:
            _, ls, lw = pairs[0]
            _, rs, rw = pairs[1]
            if abs(lw[1] - rw[1]) / max(e.distance(ls, rs), 1) > 0.28:
                low = lw if lw[1] > rw[1] else rw
                high = rw if low is lw else lw
                _add_issue(result, "knowledge_lateral_symmetry", "MATCH ARM HEIGHT",
                            "One arm is higher than the other.", "medium",
                            "Raise both arms through the same range.")
                _guide(result, low, (low[0], high[1]), "MATCH ARM HEIGHT")
        best = _side(lm, w, h)
        if best:
            _, side, *_ = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            if lean is not None and lean > 22:
                _add_issue(result, "knowledge_lateral_torso", "KEEP TORSO STILL",
                            "Torso is leaning to create extra range.", "high",
                            "Stay tall and move the arms without swinging.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "TORSO HERE")

    # SHOULDER PRESS
    elif exercise == "shoulder_press":
        best = _side(lm, w, h)
        if best:
            _, side, *_ = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            if lean is not None and lean > 24:
                _add_issue(result, "knowledge_press_back", "DO NOT LEAN BACK",
                            "Torso is leaning/arching during the press.", "high",
                            "Brace your core and keep your torso upright.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "TORSO UPRIGHT")
        lw, rw = _p(lm, e.LEFT_WRIST, w, h), _p(lm, e.RIGHT_WRIST, w, h)
        ls, rs = _p(lm, e.LEFT_SHOULDER, w, h), _p(lm, e.RIGHT_SHOULDER, w, h)
        if lw and rw and ls and rs:
            if abs(lw[1] - rw[1]) / max(e.distance(ls, rs), 1) > 0.28:
                lower = lw if lw[1] > rw[1] else rw
                upper = rw if lower is lw else lw
                _add_issue(result, "knowledge_press_symmetry", "MATCH HAND HEIGHT",
                            "One hand is higher than the other.", "medium",
                            "Press both arms through the same path.")
                _guide(result, lower, (lower[0], upper[1]), "MATCH HAND HEIGHT")
            if lw[1] > ls[1] + 0.10 * h or rw[1] > rs[1] + 0.10 * h:
                bad = lw if lw[1] > ls[1] else rw
                sh = ls if bad is lw else rs
                _add_issue(result, "knowledge_press_overhead", "PRESS HIGHER",
                            "Hand has not reached the intended overhead position.",
                            "medium", "Drive the hand upward without leaning back.")
                _guide(result, bad, (bad[0], sh[1] - 0.08 * h), "PRESS OVER SHOULDERS")

    # TRICEP EXTENSION
    elif exercise == "tricep_extension":
        for side, sid, eid in (
            ("LEFT", e.LEFT_SHOULDER, e.LEFT_ELBOW),
            ("RIGHT", e.RIGHT_SHOULDER, e.RIGHT_ELBOW),
        ):
            shoulder, elbow = _p(lm, sid, w, h), _p(lm, eid, w, h)
            hip = _p(lm, e.LEFT_HIP if side == "LEFT" else e.RIGHT_HIP, w, h)
            if shoulder and elbow and hip:
                if abs(elbow[0] - shoulder[0]) / max(e.distance(shoulder, hip), 1) > 0.62:
                    _add_issue(result, "knowledge_tricep_elbow_" + side.lower(),
                                "KEEP ELBOWS STABLE", f"{side.title()} elbow is drifting outward.",
                                "high", "Keep the upper arm controlled while the forearm moves.")
                    _guide(result, elbow, (shoulder[0], elbow[1]), "ELBOW HERE")
        best = _side(lm, w, h)
        if best:
            _, side, *_ = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            if lean is not None and lean > 25:
                _add_issue(result, "knowledge_tricep_torso", "KEEP BACK STRAIGHT",
                            "Torso is leaning to compensate.", "medium",
                            "Brace your core and keep the torso stable.")
                _guide(result, shoulder, (hip[0], shoulder[1]), "BACK HERE")

    # PUSH-UP
    elif exercise == "push_up":
        for side, sid, hid, aid, eid, wid in (
            ("LEFT", e.LEFT_SHOULDER, e.LEFT_HIP, e.LEFT_ANKLE, e.LEFT_ELBOW, e.LEFT_WRIST),
            ("RIGHT", e.RIGHT_SHOULDER, e.RIGHT_HIP, e.RIGHT_ANKLE, e.RIGHT_ELBOW, e.RIGHT_WRIST),
        ):
            shoulder, hip, ankle = (_p(lm, i, w, h) for i in (sid, hid, aid))
            if shoulder and hip and ankle:
                proj = _project(hip, shoulder, ankle)
                if proj and e.distance(hip, proj) > 0.10 * max(e.distance(shoulder, ankle), 1):
                    _add_issue(result, "knowledge_pushup_body", "KEEP BODY STRAIGHT",
                                "Hips are outside the shoulder-to-ankle line.", "high",
                                "Brace your core and keep shoulders, hips and ankles aligned.")
                    _guide(result, hip, proj, "ALIGN HIPS")
            elbow, wrist = _p(lm, eid, w, h), _p(lm, wid, w, h)
            if shoulder and elbow and wrist:
                a = _angle(shoulder, elbow, wrist)
                if a is not None and a < 55:
                    _add_issue(result, "knowledge_pushup_elbow", "CONTROL ELBOW PATH",
                                "Elbow angle is collapsing too tightly.", "medium",
                                "Keep the elbows controlled and lower smoothly.")

    # DUMBBELL ROW
    elif exercise == "dumbbell_row":
        best = _side(lm, w, h)
        if best:
            _, side, *_ = best
            lean, shoulder, hip = _torso(lm, side, w, h)
            if lean is not None and lean < 18:
                _add_issue(result, "knowledge_row_hinge", "HINGE FORWARD",
                            "Torso is too upright for the row setup.", "medium",
                            "Hinge at the hips and keep a neutral spine.")
                desired = (hip[0] + (shoulder[0] - hip[0]) * 1.45,
                           hip[1] + (shoulder[1] - hip[1]) * 1.45)
                _guide(result, shoulder, desired, "HINGE FORWARD")
            eid = e.LEFT_ELBOW if side == "LEFT" else e.RIGHT_ELBOW
            elbow = _p(lm, eid, w, h)
            if elbow and shoulder and hip and abs(elbow[0] - shoulder[0]) > 0.80 * max(e.distance(shoulder, hip), 1):
                _add_issue(result, "knowledge_row_elbow", "PULL ELBOW BACK",
                            "Elbow is drifting away from the torso path.", "medium",
                            "Drive the elbow back toward the hip.")
                _guide(result, elbow, (hip[0], elbow[1]), "ELBOW BACK")

    # SIT-UP
    elif exercise == "sit_up":
        best = _side(lm, w, h)
        if best:
            _, side, sid, hid, kid, _ = best
            shoulder, hip, knee = _p(lm, sid, w, h), _p(lm, hid, w, h), _p(lm, kid, w, h)
            if shoulder and hip and knee:
                torso_angle = _angle(shoulder, hip, knee)
                if torso_angle is not None and torso_angle < 35:
                    _add_issue(result, "knowledge_situp_control", "CONTROL THE SIT-UP",
                                "Torso is folding aggressively at the hip.", "medium",
                                "Lift and lower with controlled trunk motion.")
                    _guide(result, shoulder, (shoulder[0], shoulder[1] - 0.06 * h), "LIFT WITH CONTROL")

    # JUMPING JACK
    elif exercise == "jumping_jack":
        ls, rs = _p(lm, e.LEFT_SHOULDER, w, h), _p(lm, e.RIGHT_SHOULDER, w, h)
        lw, rw = _p(lm, e.LEFT_WRIST, w, h), _p(lm, e.RIGHT_WRIST, w, h)
        la, ra = _p(lm, e.LEFT_ANKLE, w, h), _p(lm, e.RIGHT_ANKLE, w, h)
        lh, rh = _p(lm, e.LEFT_HIP, w, h), _p(lm, e.RIGHT_HIP, w, h)
        if ls and rs and lw and rw and abs(lw[1] - rw[1]) > 0.18 * max(e.distance(ls, rs), 1):
            lower = lw if lw[1] > rw[1] else rw
            upper = rw if lower is lw else lw
            _add_issue(result, "knowledge_jack_arms", "MATCH ARM HEIGHT",
                        "Arms are opening unevenly.", "medium",
                        "Raise both arms through the same range.")
            _guide(result, lower, (lower[0], upper[1]), "MATCH ARMS")
        if la and ra and lh and rh:
            hip_w = max(e.distance(lh, rh), 1)
            if e.distance(la, ra) < 1.45 * hip_w:
                # Guide one visible foot outward. The opposite foot remains
                # untouched so the correction is not duplicated.
                _guide(result, la, (lh[0] - 0.75 * hip_w, la[1]), "OPEN LEFT LEG")
                _add_issue(result, "knowledge_jack_legs", "OPEN LEGS MORE",
                            "Legs are not reaching the open position.", "medium",
                            "Open both feet symmetrically and land softly.")


def knowledge_summary(exercise):
    return FORM_KNOWLEDGE.get(exercise, {})
