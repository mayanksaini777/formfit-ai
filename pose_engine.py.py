
# ============================================================
# AI GYM FORMFIT
# CLEAN FORM ENGINE + ORIGINAL SIMPLE UI
# VERSION: V3 STRONG FORM CHECK
#
# Controls:
#   1 Bicep Curl
#   2 Squat
#   3 Shoulder Press
#   4 Lateral Raise
#   5 Tricep Extension
#   6 Lunge
#   7 Push Up
#   8 Dumbbell Row
#   9 Sit Up
#   0 Jumping Jack
#   R Reset reps
#   Q Quit
#
# COLORS:
#   GREEN = correct
#   RED = wrong
#   YELLOW DOTTED = target/correction
# ============================================================

import cv2
import math
import time
import mediapipe as mp


# ============================================================
# MEDIAPIPE
# ============================================================

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
PL = mp_pose.PoseLandmark


# ============================================================
# COLORS - BGR
# ============================================================

GREEN = (0, 255, 0)
YELLOW = (0, 220, 255)
RED = (0, 0, 255)
WHITE = (255, 255, 255)
CYAN = (255, 255, 0)
BLUE = (255, 150, 0)
BLACK = (0, 0, 0)
DARK = (10, 15, 20)
GRAY = (80, 80, 80)


# ============================================================
# LANDMARKS
# ============================================================

LEFT_EAR = PL.LEFT_EAR.value
RIGHT_EAR = PL.RIGHT_EAR.value

LEFT_SHOULDER = PL.LEFT_SHOULDER.value
RIGHT_SHOULDER = PL.RIGHT_SHOULDER.value

LEFT_ELBOW = PL.LEFT_ELBOW.value
RIGHT_ELBOW = PL.RIGHT_ELBOW.value

LEFT_WRIST = PL.LEFT_WRIST.value
RIGHT_WRIST = PL.RIGHT_WRIST.value

LEFT_HIP = PL.LEFT_HIP.value
RIGHT_HIP = PL.RIGHT_HIP.value

LEFT_KNEE = PL.LEFT_KNEE.value
RIGHT_KNEE = PL.RIGHT_KNEE.value

LEFT_ANKLE = PL.LEFT_ANKLE.value
RIGHT_ANKLE = PL.RIGHT_ANKLE.value


# ============================================================
# EXERCISES
# ============================================================

EXERCISES = {
    "squat": "SQUAT",
    "bicep_curls": "BICEP CURL",
    "shoulder_press": "SHOULDER PRESS",
    "lateral_shoulder_raises": "LATERAL RAISE",
    "tricep_extension": "TRICEP EXTENSION",
    "lunges": "LUNGE",
    "push_up": "PUSH UP",
    "dumbbell_row": "DUMBBELL ROW",
    "sit_up": "SIT UP",
    "jumping_jack": "JUMPING JACK",
}

ALIASES = {
    "squat": "squat",
    "squats": "squat",
    "bicep curl": "bicep_curls",
    "biceps curl": "bicep_curls",
    "bicep curls": "bicep_curls",
    "biceps curls": "bicep_curls",
    "curl": "bicep_curls",
    "shoulder press": "shoulder_press",
    "shoulder presses": "shoulder_press",
    "lateral raise": "lateral_shoulder_raises",
    "lateral raises": "lateral_shoulder_raises",
    "lateral shoulder raise": "lateral_shoulder_raises",
    "tricep extension": "tricep_extension",
    "triceps extension": "tricep_extension",
    "lunge": "lunges",
    "lunges": "lunges",
    "push up": "push_up",
    "push-up": "push_up",
    "push ups": "push_up",
    "pushups": "push_up",
    "dumbbell row": "dumbbell_row",
    "row": "dumbbell_row",
    "sit up": "sit_up",
    "sit-up": "sit_up",
    "sit ups": "sit_up",
    "jumping jack": "jumping_jack",
    "jumping jacks": "jumping_jack",
}


def normalize_exercise(name):
    name = name.strip().lower()
    return ALIASES.get(name, name.replace(" ", "_"))


# ============================================================
# BASIC MATH
# ============================================================

def visible(landmarks, index, threshold=0.50):
    try:
        lm = landmarks[index]
        return (
            float(lm.visibility) >= threshold
            and math.isfinite(float(lm.x))
            and math.isfinite(float(lm.y))
        )
    except Exception:
        return False


def xy(landmarks, index, width, height):
    lm = landmarks[index]
    return (
        int(max(0, min(width - 1, lm.x * width))),
        int(max(0, min(height - 1, lm.y * height))),
    )


def distance(a, b):
    return math.hypot(
        a[0] - b[0],
        a[1] - b[1],
    )


def angle(a, b, c):
    bax = a[0] - b[0]
    bay = a[1] - b[1]
    bcx = c[0] - b[0]
    bcy = c[1] - b[1]

    m1 = math.hypot(bax, bay)
    m2 = math.hypot(bcx, bcy)

    if m1 < 1e-6 or m2 < 1e-6:
        return None

    value = (bax * bcx + bay * bcy) / (m1 * m2)
    value = max(-1.0, min(1.0, value))

    return math.degrees(math.acos(value))


def vertical_angle(a, b):
    dx = abs(b[0] - a[0])
    dy = abs(b[1] - a[1])
    return math.degrees(math.atan2(dx, dy + 1e-6))


def midpoint(a, b):
    return (
        (a[0] + b[0]) // 2,
        (a[1] + b[1]) // 2,
    )


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ============================================================
# RESULT
# ============================================================

class FormResult:

    def __init__(
        self,
        status="red",
        message="BODY NOT DETECTED",
        score=0,
        angles=None,
        pipes=None,
        targets=None,
        view="SIDE",
        good_rep=False,
    ):
        self.status = status
        self.message = message
        self.score = score
        self.angles = angles or {}
        self.pipes = pipes or []
        self.targets = targets or []
        self.view = view
        self.good_rep = good_rep


# ============================================================
# VIEW DETECTION
# ============================================================

def detect_view(landmarks, width, height):
    required = [
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
        LEFT_HIP,
        RIGHT_HIP,
    ]

    if not all(visible(landmarks, i, 0.35) for i in required):
        return "SIDE"

    ls = xy(landmarks, LEFT_SHOULDER, width, height)
    rs = xy(landmarks, RIGHT_SHOULDER, width, height)
    lh = xy(landmarks, LEFT_HIP, width, height)
    rh = xy(landmarks, RIGHT_HIP, width, height)

    shoulder_width = distance(ls, rs)
    torso_width = distance(lh, rh)
    torso_length = max(
        distance(midpoint(ls, rs), midpoint(lh, rh)),
        1,
    )

    # Front view normally exposes both shoulders/hips much wider.
    ratio = shoulder_width / torso_length

    if ratio > 0.62 and torso_width > 0.35 * torso_length:
        return "FRONT"

    return "SIDE"


# ============================================================
# DRAWING
# ============================================================

def draw_pipe(frame, a, b, color, thickness=6):
    cv2.line(
        frame,
        a,
        b,
        color,
        thickness,
        cv2.LINE_AA,
    )

    cv2.circle(
        frame,
        a,
        6,
        WHITE,
        -1,
        cv2.LINE_AA,
    )

    cv2.circle(
        frame,
        b,
        6,
        WHITE,
        -1,
        cv2.LINE_AA,
    )


def draw_dotted(frame, a, b, color=YELLOW, thickness=5):
    length = distance(a, b)

    if length < 2:
        return

    dx = (b[0] - a[0]) / length
    dy = (b[1] - a[1]) / length

    current = 0

    while current < length:
        end = min(current + 10, length)

        p1 = (
            int(a[0] + dx * current),
            int(a[1] + dy * current),
        )
        p2 = (
            int(a[0] + dx * end),
            int(a[1] + dy * end),
        )

        cv2.line(
            frame,
            p1,
            p2,
            color,
            thickness,
            cv2.LINE_AA,
        )

        current += 20


def draw_target(frame, actual, desired, label=""):
    draw_dotted(
        frame,
        actual,
        desired,
        YELLOW,
        5,
    )

    cv2.circle(
        frame,
        desired,
        10,
        DARK,
        -1,
        cv2.LINE_AA,
    )

    cv2.circle(
        frame,
        desired,
        7,
        YELLOW,
        2,
        cv2.LINE_AA,
    )

    if label:
        cv2.putText(
            frame,
            label,
            (desired[0] + 8, desired[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            YELLOW,
            1,
            cv2.LINE_AA,
        )


def draw_arrow(frame, start, end, color=YELLOW):
    cv2.arrowedLine(
        frame,
        start,
        end,
        color,
        4,
        cv2.LINE_AA,
        tipLength=0.25,
    )


def draw_skeleton(frame, landmarks):
    h, w = frame.shape[:2]

    connections = [
        (LEFT_SHOULDER, RIGHT_SHOULDER),
        (LEFT_SHOULDER, LEFT_ELBOW),
        (LEFT_ELBOW, LEFT_WRIST),
        (RIGHT_SHOULDER, RIGHT_ELBOW),
        (RIGHT_ELBOW, RIGHT_WRIST),
        (LEFT_SHOULDER, LEFT_HIP),
        (RIGHT_SHOULDER, RIGHT_HIP),
        (LEFT_HIP, RIGHT_HIP),
        (LEFT_HIP, LEFT_KNEE),
        (LEFT_KNEE, LEFT_ANKLE),
        (RIGHT_HIP, RIGHT_KNEE),
        (RIGHT_KNEE, RIGHT_ANKLE),
    ]

    for a, b in connections:
        if visible(landmarks, a) and visible(landmarks, b):
            draw_pipe(
                frame,
                xy(landmarks, a, w, h),
                xy(landmarks, b, w, h),
                GREEN,
                5,
            )


# ============================================================
# PIPE HELPERS
# ============================================================

def status_color(status):
    if status == "green":
        return GREEN
    if status == "yellow":
        return YELLOW
    return RED


def add_pipe(pipes, a, b, status):
    pipes.append((a, b, status))


def ideal_back_target(shoulder, hip, exercise):
    length = max(distance(shoulder, hip), 100)

    if exercise in (
        "squat",
        "lunges",
        "dumbbell_row",
    ):
        # A squat/row can lean forward, but not collapse.
        dx = shoulder[0] - hip[0]
        target_x = int(
            hip[0] + clamp(dx, -0.40 * length, 0.40 * length)
        )
        target_y = int(hip[1] - 0.95 * length)
        return target_x, target_y

    return (
        hip[0],
        int(hip[1] - length),
    )


# ============================================================
# BACK / CHEST
# ============================================================

def analyze_back(landmarks, side, width, height, exercise):
    if side == "FRONT":
        ls = xy(landmarks, LEFT_SHOULDER, width, height)
        rs = xy(landmarks, RIGHT_SHOULDER, width, height)
        lh = xy(landmarks, LEFT_HIP, width, height)
        rh = xy(landmarks, RIGHT_HIP, width, height)

        shoulder_y_diff = abs(ls[1] - rs[1])
        hip_y_diff = abs(lh[1] - rh[1])

        scale = max(distance(ls, rs), 1)

        if shoulder_y_diff <= 0.12 * scale and hip_y_diff <= 0.15 * scale:
            return "green", "CHEST / SHOULDERS ALIGNED", 98, []

        return (
            "yellow",
            "KEEP CHEST LEVEL",
            78,
            [],
        )

    ear_id = RIGHT_EAR if side == "RIGHT" else LEFT_EAR
    shoulder_id = RIGHT_SHOULDER if side == "RIGHT" else LEFT_SHOULDER
    hip_id = RIGHT_HIP if side == "RIGHT" else LEFT_HIP

    if not (
        visible(landmarks, ear_id, 0.35)
        and visible(landmarks, shoulder_id, 0.35)
        and visible(landmarks, hip_id, 0.35)
    ):
        return "yellow", "SIDE VIEW: SHOW EAR / SHOULDER / HIP", 70, []

    ear = xy(landmarks, ear_id, width, height)
    shoulder = xy(landmarks, shoulder_id, width, height)
    hip = xy(landmarks, hip_id, width, height)

    torso_angle = angle(
        ear,
        shoulder,
        hip,
    )

    if torso_angle is None:
        return "yellow", "KEEP BACK CONTROLLED", 70, []

    if exercise in ("squat", "lunges", "dumbbell_row"):
        if torso_angle >= 145:
            return "green", "BACK ALIGNMENT GOOD", 98, []
        if torso_angle >= 120:
            return "yellow", "STRAIGHTEN YOUR BACK", 78, []
        return "red", "KEEP YOUR BACK STRAIGHT", 50, []

    if torso_angle >= 155:
        return "green", "BACK ALIGNMENT GOOD", 98, []

    if torso_angle >= 140:
        return "yellow", "STRAIGHTEN YOUR BACK", 78, []

    return "red", "KEEP YOUR TORSO UPRIGHT", 50, []


# ============================================================
# BICEP CURL
# ============================================================

def analyze_bicep(landmarks, width, height):
    view = detect_view(landmarks, width, height)
    pipes = []
    targets = []
    feedback = []

    # FRONT VIEW: analyze BOTH arms.
    if view == "FRONT":
        ids = [
            (
                LEFT_SHOULDER,
                LEFT_ELBOW,
                LEFT_WRIST,
                "LEFT",
            ),
            (
                RIGHT_SHOULDER,
                RIGHT_ELBOW,
                RIGHT_WRIST,
                "RIGHT",
            ),
        ]

        angles = []
        elbow_bad_count = 0

        for sid, eid, wid, name in ids:
            if not (
                visible(landmarks, sid)
                and visible(landmarks, eid)
                and visible(landmarks, wid)
            ):
                return FormResult(
                    "red",
                    "BOTH ARMS MUST BE VISIBLE",
                    0,
                    view="FRONT",
                )

            shoulder = xy(landmarks, sid, width, height)
            elbow = xy(landmarks, eid, width, height)
            wrist = xy(landmarks, wid, width, height)

            a = angle(
                shoulder,
                elbow,
                wrist,
            )

            angles.append(a)

            shoulder_width = max(
                distance(
                    xy(landmarks, LEFT_SHOULDER, width, height),
                    xy(landmarks, RIGHT_SHOULDER, width, height),
                ),
                1,
            )

            elbow_out = abs(
                elbow[0] - shoulder[0]
            ) / shoulder_width

            # Front-view curl: elbow should remain reasonably
            # close to shoulder's vertical line.
            bad = elbow_out > 0.55

            add_pipe(
                pipes,
                shoulder,
                elbow,
                "red" if bad else "green",
            )
            add_pipe(
                pipes,
                elbow,
                wrist,
                "green",
            )

            if bad:
                elbow_bad_count += 1
                desired = (
                    shoulder[0],
                    elbow[1],
                )
                targets.append(
                    (
                        elbow,
                        desired,
                        f"{name} ELBOW",
                    )
                )
                feedback.append(
                    f"Keep {name.lower()} elbow close."
                )

        symmetry = abs(
            angles[0] - angles[1]
        ) <= 20

        if not symmetry:
            feedback.append("Curl both arms evenly.")

        if elbow_bad_count:
            status = "red"
            message = "KEEP ELBOWS FIXED"
        elif not symmetry:
            status = "yellow"
            message = "KEEP BOTH ARMS EVEN"
        else:
            status = "green"
            message = "CORRECT BICEP CURL"

        checks = [
            elbow_bad_count == 0,
            symmetry,
        ]

        score = round(
            100 * sum(checks) / len(checks)
        )

        value = sum(angles) / len(angles)

        return FormResult(
            status,
            message,
            score,
            {"elbow": value},
            pipes,
            targets,
            view,
            score >= 85,
        )

    # SIDE VIEW: use the clearer side, but do not pretend
    # the hidden elbow is measurable.
    side = "RIGHT"
    if (
        visible(landmarks, LEFT_SHOULDER)
        and visible(landmarks, LEFT_ELBOW)
        and visible(landmarks, LEFT_WRIST)
    ):
        left_visibility = (
            landmarks[LEFT_SHOULDER].visibility
            + landmarks[LEFT_ELBOW].visibility
            + landmarks[LEFT_WRIST].visibility
        )
    else:
        left_visibility = 0

    if (
        visible(landmarks, RIGHT_SHOULDER)
        and visible(landmarks, RIGHT_ELBOW)
        and visible(landmarks, RIGHT_WRIST)
    ):
        right_visibility = (
            landmarks[RIGHT_SHOULDER].visibility
            + landmarks[RIGHT_ELBOW].visibility
            + landmarks[RIGHT_WRIST].visibility
        )
    else:
        right_visibility = 0

    if left_visibility > right_visibility:
        side = "LEFT"

    if side == "LEFT":
        sid, eid, wid = LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST
    else:
        sid, eid, wid = RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST

    if not (
        visible(landmarks, sid)
        and visible(landmarks, eid)
        and visible(landmarks, wid)
    ):
        return FormResult(
            "red",
            "SHOW YOUR ARM CLEARLY",
            0,
            view="SIDE",
        )

    shoulder = xy(landmarks, sid, width, height)
    elbow = xy(landmarks, eid, width, height)
    wrist = xy(landmarks, wid, width, height)

    a = angle(
        shoulder,
        elbow,
        wrist,
    )

    upper_arm_tilt = vertical_angle(
        shoulder,
        elbow,
    )

    torso_status, torso_message, torso_score, _ = analyze_back(
        landmarks,
        side,
        width,
        height,
        "bicep_curls",
    )

    elbow_offset = abs(
        elbow[0] - shoulder[0]
    )

    hip_id = (
        LEFT_HIP
        if side == "LEFT"
        else RIGHT_HIP
    )

    hip = xy(
        landmarks,
        hip_id,
        width,
        height,
    )

    torso_length = max(
        distance(shoulder, hip),
        1,
    )

    # Scale-independent elbow stability:
    # the same person can appear at different camera distances.
    elbow_ratio = elbow_offset / torso_length

    elbow_bad = (
        upper_arm_tilt > 48
        or elbow_ratio > 0.52
    )

    add_pipe(
        pipes,
        shoulder,
        elbow,
        "red" if elbow_bad else "green",
    )
    add_pipe(
        pipes,
        elbow,
        wrist,
        "green",
    )

    if elbow_bad:
        desired = (
            shoulder[0],
            int(
                shoulder[1]
                + distance(shoulder, elbow) * 0.90
            ),
        )
        targets.append(
            (
                elbow,
                desired,
                "ELBOW HERE",
            )
        )
        feedback.append("Keep your elbow close to your body.")

    if torso_status != "green":
        torso_should = xy(
            landmarks,
            LEFT_SHOULDER if side == "LEFT" else RIGHT_SHOULDER,
            width,
            height,
        )
        torso_hip = xy(
            landmarks,
            LEFT_HIP if side == "LEFT" else RIGHT_HIP,
            width,
            height,
        )
        desired = ideal_back_target(
            torso_should,
            torso_hip,
            "bicep_curls",
        )
        targets.append(
            (
                torso_should,
                desired,
                "STRAIGHT BACK",
            )
        )
        feedback.append(torso_message)

    if elbow_bad:
        status = "red"
        message = "KEEP YOUR ELBOW FIXED"
    elif torso_status == "red":
        status = "red"
        message = torso_message
    elif torso_status == "yellow":
        status = "yellow"
        message = torso_message
    elif a <= 85:
        status = "green"
        message = "GOOD CURL"
    elif a >= 140:
        status = "green"
        message = "GOOD EXTENSION"
    elif a <= 105:
        status = "yellow"
        message = "CURL A LITTLE MORE"
    else:
        status = "yellow"
        message = "CONTROL YOUR CURL"

    arm_score = (
        98 if not elbow_bad else 55
    )

    score = min(
        arm_score,
        torso_score,
    )

    return FormResult(
        status,
        message,
        score,
        {"elbow": a},
        pipes,
        targets,
        view,
        status == "green" and score >= 85,
    )


# ============================================================
# SQUAT
# ============================================================

def analyze_squat(landmarks, width, height):
    # Side is preferred because squat depth/back are best from side.
    side = "RIGHT"

    right_vis = (
        landmarks[RIGHT_HIP].visibility
        + landmarks[RIGHT_KNEE].visibility
        + landmarks[RIGHT_ANKLE].visibility
    )
    left_vis = (
        landmarks[LEFT_HIP].visibility
        + landmarks[LEFT_KNEE].visibility
        + landmarks[LEFT_ANKLE].visibility
    )

    if left_vis > right_vis:
        side = "LEFT"

    if side == "LEFT":
        hid, kid, aid = LEFT_HIP, LEFT_KNEE, LEFT_ANKLE
    else:
        hid, kid, aid = RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE

    needed = [hid, kid, aid]
    if not all(visible(landmarks, i) for i in needed):
        return FormResult(
            "red",
            "SHOW YOUR FULL LEG",
            0,
            view="SIDE",
        )

    hip = xy(landmarks, hid, width, height)
    knee = xy(landmarks, kid, width, height)
    ankle = xy(landmarks, aid, width, height)

    knee_angle = angle(
        hip,
        knee,
        ankle,
    )

    if knee_angle is None:
        return FormResult(
            "red",
            "LEG NOT CLEAR",
            0,
            view="SIDE",
        )

    torso_status, torso_message, torso_score, _ = analyze_back(
        landmarks,
        side,
        width,
        height,
        "squat",
    )

    pipes = []
    targets = []

    add_pipe(
        pipes,
        hip,
        knee,
        "green",
    )
    add_pipe(
        pipes,
        knee,
        ankle,
        "green",
    )

    knee_to_ankle = abs(
        knee[0] - ankle[0]
    )

    leg_length = max(
        distance(knee, ankle),
        1,
    )

    knee_bad = (
        knee_to_ankle / leg_length > 0.70
    )

    if knee_bad:
        desired = (
            ankle[0],
            knee[1],
        )
        add_pipe(
            pipes,
            hip,
            knee,
            "red",
        )
        targets.append(
            (
                knee,
                desired,
                "KNEE TRACK HERE",
            )
        )

    if knee_angle <= 105:
        depth_status = "green"
        depth_message = "GOOD SQUAT DEPTH"
        depth_score = 98
    elif knee_angle <= 125:
        depth_status = "yellow"
        depth_message = "GO A LITTLE DEEPER"
        depth_score = 82
    else:
        depth_status = "yellow"
        depth_message = "BEND YOUR KNEES MORE"
        depth_score = 68

        desired = (
            hip[0],
            int(
                hip[1]
                + distance(hip, knee) * 0.20
            ),
        )
        targets.append(
            (
                hip,
                desired,
                "LOWER",
            )
        )

    if torso_status == "red":
        status = "red"
        message = torso_message
    elif knee_bad:
        status = "red"
        message = "KEEP KNEE ALIGNED"
    elif torso_status == "yellow":
        status = "yellow"
        message = torso_message
    else:
        status = depth_status
        message = depth_message

    score = min(
        depth_score,
        torso_score,
        55 if knee_bad else 98,
    )

    return FormResult(
        status,
        message,
        score,
        {"knee": knee_angle},
        pipes,
        targets,
        "SIDE",
        status == "green" and score >= 85,
    )


# ============================================================
# SHOULDER PRESS
# ============================================================

def analyze_shoulder_press(landmarks, width, height):
    view = detect_view(landmarks, width, height)
    pipes = []
    targets = []
    angles = []

    pairs = [
        (
            LEFT_SHOULDER,
            LEFT_ELBOW,
            LEFT_WRIST,
            "LEFT",
        ),
        (
            RIGHT_SHOULDER,
            RIGHT_ELBOW,
            RIGHT_WRIST,
            "RIGHT",
        ),
    ]

    for sid, eid, wid, name in pairs:
        if not (
            visible(landmarks, sid)
            and visible(landmarks, eid)
            and visible(landmarks, wid)
        ):
            return FormResult(
                "red",
                "BOTH ARMS MUST BE VISIBLE",
                0,
                view=view,
            )

        s = xy(landmarks, sid, width, height)
        e = xy(landmarks, eid, width, height)
        w = xy(landmarks, wid, width, height)

        a = angle(s, e, w)
        angles.append(a)

        add_pipe(
            pipes,
            s,
            e,
            "green",
        )
        add_pipe(
            pipes,
            e,
            w,
            "green",
        )

        if w[1] > s[1] - 25:
            desired = (
                s[0],
                max(25, s[1] - 160),
            )
            targets.append(
                (
                    w,
                    desired,
                    f"{name} HAND UP",
                )
            )

    left_up = angles[0] is not None and (
        xy(landmarks, LEFT_WRIST, width, height)[1]
        <
        xy(landmarks, LEFT_SHOULDER, width, height)[1] - 25
    )

    right_up = angles[1] is not None and (
        xy(landmarks, RIGHT_WRIST, width, height)[1]
        <
        xy(landmarks, RIGHT_SHOULDER, width, height)[1] - 25
    )

    symmetry = abs(angles[0] - angles[1]) <= 20

    side = "RIGHT"
    torso_status, torso_message, torso_score, _ = analyze_back(
        landmarks,
        side,
        width,
        height,
        "shoulder_press",
    )

    if torso_status == "red":
        status = "red"
        message = torso_message
    elif not symmetry:
        status = "red"
        message = "KEEP BOTH ARMS EVEN"
    elif left_up and right_up:
        status = "green"
        message = "GOOD PRESS"
    else:
        status = "yellow"
        message = "PRESS BOTH HANDS UP"

    score = min(
        torso_score,
        98 if symmetry else 55,
        98 if left_up and right_up else 70,
    )

    return FormResult(
        status,
        message,
        score,
        {"elbow": (angles[0] + angles[1]) / 2},
        pipes,
        targets,
        view,
        status == "green" and score >= 85,
    )


# ============================================================
# LATERAL RAISE
# ============================================================

def analyze_lateral(landmarks, width, height):
    pairs = [
        (LEFT_SHOULDER, LEFT_ELBOW, "LEFT"),
        (RIGHT_SHOULDER, RIGHT_ELBOW, "RIGHT"),
    ]

    pipes = []
    targets = []
    values = []

    for sid, eid, name in pairs:
        if not (
            visible(landmarks, sid)
            and visible(landmarks, eid)
        ):
            return FormResult(
                "red",
                "BOTH ARMS MUST BE VISIBLE",
                0,
                view="FRONT",
            )

        s = xy(landmarks, sid, width, height)
        e = xy(landmarks, eid, width, height)

        value = vertical_angle(s, e)
        values.append(value)

        add_pipe(
            pipes,
            s,
            e,
            "green",
        )

        # Shoulder-height target.
        if not 65 <= value <= 100:
            desired = (
                e[0],
                s[1],
            )
            targets.append(
                (
                    e,
                    desired,
                    f"{name} SHOULDER HEIGHT",
                )
            )

    symmetry = abs(values[0] - values[1]) <= 18
    good_height = 65 <= sum(values) / 2 <= 100

    if not symmetry:
        status = "red"
        message = "RAISE BOTH ARMS EVENLY"
    elif good_height:
        status = "green"
        message = "GOOD LATERAL RAISE"
    else:
        status = "yellow"
        message = "MOVE TO SHOULDER HEIGHT"

    score = (
        98
        if symmetry and good_height
        else 72
        if symmetry
        else 55
    )

    return FormResult(
        status,
        message,
        score,
        {"raise": sum(values) / 2},
        pipes,
        targets,
        "FRONT",
        status == "green" and score >= 85,
    )


# ============================================================
# TRICEP / LUNGE / PUSH-UP / ROW / SIT-UP / JACK
# ============================================================

def analyze_tricep(landmarks, width, height):
    # Use the better visible side.
    side = choose_side(landmarks)

    if side == "LEFT":
        sid, eid, wid = LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST
    else:
        sid, eid, wid = RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST

    if not all(
        visible(landmarks, i)
        for i in (sid, eid, wid)
    ):
        return FormResult("red", "SHOW YOUR ARM", 0, view="SIDE")

    s = xy(landmarks, sid, width, height)
    e = xy(landmarks, eid, width, height)
    w = xy(landmarks, wid, width, height)

    a = angle(s, e, w)
    pipes = [(s, e, "green"), (e, w, "green")]
    targets = []

    if a > 115:
        desired = (
            s[0],
            int(s[1] + distance(s, e) * 0.95),
        )
        pipes[0] = (s, e, "red")
        targets.append((e, desired, "EXTEND ELBOW"))

    status = "green" if a <= 75 else "yellow"
    message = "GOOD EXTENSION" if status == "green" else "EXTEND YOUR ARM MORE"

    return FormResult(
        status,
        message,
        98 if status == "green" else 78,
        {"elbow": a},
        pipes,
        targets,
        "SIDE",
        status == "green",
    )


def analyze_lunge(landmarks, width, height):
    side = choose_side(landmarks)

    if side == "LEFT":
        hid, kid, aid = LEFT_HIP, LEFT_KNEE, LEFT_ANKLE
    else:
        hid, kid, aid = RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE

    if not all(visible(landmarks, i) for i in (hid, kid, aid)):
        return FormResult("red", "SHOW FULL LEG", 0, view="SIDE")

    h = xy(landmarks, hid, width, height)
    k = xy(landmarks, kid, width, height)
    a = xy(landmarks, aid, width, height)

    knee = angle(h, k, a)
    pipes = [(h, k, "green"), (k, a, "green")]
    targets = []

    if knee > 125:
        desired = (
            k[0],
            int(k[1] + 30),
        )
        targets.append((k, desired, "LOWER"))

    status = "green" if knee <= 105 else "yellow"
    message = "GOOD LUNGE" if status == "green" else "BEND FRONT KNEE"

    return FormResult(
        status,
        message,
        98 if status == "green" else 75,
        {"knee": knee},
        pipes,
        targets,
        "SIDE",
        status == "green",
    )


def analyze_pushup(landmarks, width, height):
    side = choose_side(landmarks)

    if side == "LEFT":
        sid, eid, wid, hid, kid = (
            LEFT_SHOULDER,
            LEFT_ELBOW,
            LEFT_WRIST,
            LEFT_HIP,
            LEFT_KNEE,
        )
    else:
        sid, eid, wid, hid, kid = (
            RIGHT_SHOULDER,
            RIGHT_ELBOW,
            RIGHT_WRIST,
            RIGHT_HIP,
            RIGHT_KNEE,
        )

    if not all(
        visible(landmarks, i)
        for i in (sid, eid, wid, hid, kid)
    ):
        return FormResult("red", "SHOW YOUR FULL BODY", 0, view="SIDE")

    s = xy(landmarks, sid, width, height)
    e = xy(landmarks, eid, width, height)
    w = xy(landmarks, wid, width, height)
    h = xy(landmarks, hid, width, height)
    k = xy(landmarks, kid, width, height)

    elbow = angle(s, e, w)
    body = angle(s, h, k)

    pipes = [
        (s, e, "green"),
        (e, w, "green"),
        (s, h, "green"),
        (h, k, "green"),
    ]
    targets = []

    if body < 155:
        pipes[2] = (s, h, "red")
        desired = (
            h[0],
            int((s[1] + k[1]) / 2),
        )
        targets.append((h, desired, "STRAIGHT BODY"))

    if elbow > 130:
        pipes[0] = (s, e, "red")
        targets.append(
            (
                e,
                (e[0], int(e[1] + 30)),
                "LOWER",
            )
        )

    if body < 155:
        status, message = "red", "STRAIGHTEN YOUR BODY"
    elif elbow <= 110:
        status, message = "green", "GOOD PUSH-UP"
    else:
        status, message = "yellow", "LOWER YOUR BODY"

    score = min(
        98 if body >= 155 else 55,
        98 if elbow <= 110 else 75,
    )

    return FormResult(
        status,
        message,
        score,
        {"elbow": elbow, "hip": body},
        pipes,
        targets,
        "SIDE",
        status == "green",
    )


def analyze_row(landmarks, width, height):
    side = choose_side(landmarks)

    if side == "LEFT":
        sid, eid, wid, hid = LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST, LEFT_HIP
    else:
        sid, eid, wid, hid = RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST, RIGHT_HIP

    if not all(visible(landmarks, i) for i in (sid, eid, wid, hid)):
        return FormResult("red", "SHOW ARM AND HIP", 0, view="SIDE")

    s = xy(landmarks, sid, width, height)
    e = xy(landmarks, eid, width, height)
    w = xy(landmarks, wid, width, height)
    h = xy(landmarks, hid, width, height)

    elbow = angle(s, e, w)
    torso = vertical_angle(s, h)

    pipes = [
        (s, e, "green"),
        (e, w, "green"),
        (s, h, "green"),
    ]
    targets = []

    if elbow > 120:
        pipes[0] = (s, e, "red")
        targets.append(
            (
                e,
                (int((s[0] + h[0]) / 2), e[1]),
                "PULL ELBOW",
            )
        )

    if torso > 30:
        pipes[2] = (s, h, "red")
        targets.append(
            (
                s,
                (h[0], int(h[1] - distance(s, h))),
                "BACK",
            )
        )

    if torso > 30:
        status, message = "red", "STRAIGHTEN YOUR BACK"
    elif elbow <= 105:
        status, message = "green", "GOOD ROW"
    else:
        status, message = "yellow", "PULL ELBOW BACK"

    score = min(
        98 if elbow <= 105 else 72,
        98 if torso <= 30 else 55,
    )

    return FormResult(
        status,
        message,
        score,
        {"elbow": elbow},
        pipes,
        targets,
        "SIDE",
        status == "green",
    )


def analyze_situp(landmarks, width, height):
    side = choose_side(landmarks)

    if side == "LEFT":
        sid, hid, kid = LEFT_SHOULDER, LEFT_HIP, LEFT_KNEE
    else:
        sid, hid, kid = RIGHT_SHOULDER, RIGHT_HIP, RIGHT_KNEE

    if not all(visible(landmarks, i) for i in (sid, hid, kid)):
        return FormResult("red", "SHOW SIDE BODY", 0, view="SIDE")

    s = xy(landmarks, sid, width, height)
    h = xy(landmarks, hid, width, height)
    k = xy(landmarks, kid, width, height)

    hip = angle(s, h, k)

    pipes = [(s, h, "green"), (h, k, "green")]

    status = "green" if hip < 100 else "yellow"
    message = "GOOD SIT-UP POSITION" if status == "green" else "LIFT TORSO"

    return FormResult(
        status,
        message,
        98 if status == "green" else 75,
        {"hip": hip},
        pipes,
        [],
        "SIDE",
        status == "green",
    )


def analyze_jumping_jack(landmarks, width, height):
    required = [
        LEFT_WRIST,
        RIGHT_WRIST,
        LEFT_ANKLE,
        RIGHT_ANKLE,
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
    ]

    if not all(visible(landmarks, i) for i in required):
        return FormResult("red", "SHOW BOTH ARMS AND LEGS", 0, view="FRONT")

    lw = xy(landmarks, LEFT_WRIST, width, height)
    rw = xy(landmarks, RIGHT_WRIST, width, height)
    ls = xy(landmarks, LEFT_SHOULDER, width, height)
    rs = xy(landmarks, RIGHT_SHOULDER, width, height)

    shoulder_width = max(distance(ls, rs), 1)

    arms_open = (
        abs(lw[0] - rw[0])
        >
        1.7 * shoulder_width
    )

    pipes = [
        (ls, lw, "green"),
        (rs, rw, "green"),
    ]

    status = "green" if arms_open else "yellow"
    message = "GOOD JACK POSITION" if arms_open else "OPEN YOUR ARMS"

    return FormResult(
        status,
        message,
        98 if arms_open else 75,
        {},
        pipes,
        [],
        "FRONT",
        status == "green",
    )


def choose_side(landmarks):
    left = sum(
        float(landmarks[i].visibility)
        for i in (
            LEFT_EAR,
            LEFT_SHOULDER,
            LEFT_ELBOW,
            LEFT_WRIST,
            LEFT_HIP,
            LEFT_KNEE,
            LEFT_ANKLE,
        )
    )

    right = sum(
        float(landmarks[i].visibility)
        for i in (
            RIGHT_EAR,
            RIGHT_SHOULDER,
            RIGHT_ELBOW,
            RIGHT_WRIST,
            RIGHT_HIP,
            RIGHT_KNEE,
            RIGHT_ANKLE,
        )
    )

    return "LEFT" if left > right else "RIGHT"


# ============================================================
# DISPATCH
# ============================================================

def analyze_exercise(exercise, landmarks, width, height):
    if exercise == "bicep_curls":
        return analyze_bicep(landmarks, width, height)

    if exercise == "squat":
        return analyze_squat(landmarks, width, height)

    if exercise == "shoulder_press":
        return analyze_shoulder_press(landmarks, width, height)

    if exercise == "lateral_shoulder_raises":
        return analyze_lateral(landmarks, width, height)

    if exercise == "tricep_extension":
        return analyze_tricep(landmarks, width, height)

    if exercise == "lunges":
        return analyze_lunge(landmarks, width, height)

    if exercise == "push_up":
        return analyze_pushup(landmarks, width, height)

    if exercise == "dumbbell_row":
        return analyze_row(landmarks, width, height)

    if exercise == "sit_up":
        return analyze_situp(landmarks, width, height)

    if exercise == "jumping_jack":
        return analyze_jumping_jack(landmarks, width, height)

    return FormResult(
        "yellow",
        "EXERCISE RULE NOT READY",
        70,
    )


# ============================================================
# CORRECTION GUIDE
# ============================================================

def draw_correction_guides(frame, result):
    if result.status == "green":
        return

    for actual, desired, label in result.targets:
        draw_target(
            frame,
            actual,
            desired,
            label,
        )
        draw_arrow(
            frame,
            actual,
            desired,
            YELLOW,
        )



# ============================================================
# TEMPORAL STABILITY ENGINE
# ============================================================
#
# The camera produces noisy landmark positions frame-by-frame.
# V4 does not make a hard form decision from one frame.
#
# Layers:
#   A. Landmark EMA smoothing
#   B. Score EMA smoothing
#   C. Status hysteresis / consecutive-frame confirmation
#   D. Target-point smoothing
#
# This makes the visual correction much less "flickery" and
# prevents one bad frame from immediately becoming RED.
# ============================================================

class LandmarkSmoother:
    def __init__(self, alpha=0.42):
        self.alpha = alpha
        self.previous = {}

    def reset(self):
        self.previous.clear()

    def update(self, landmarks):
        # Return a lightweight list of landmark-like objects.
        # We keep the original MediaPipe objects and smooth x/y
        # while preserving visibility/presence.
        smoothed = []

        for i, lm in enumerate(landmarks):
            old = self.previous.get(i)

            if old is None:
                x = float(lm.x)
                y = float(lm.y)
            else:
                a = self.alpha
                x = a * float(lm.x) + (1.0 - a) * old[0]
                y = a * float(lm.y) + (1.0 - a) * old[1]

            self.previous[i] = (x, y)

            # Simple proxy object; MediaPipe landmark attributes
            # used by this engine are x/y/visibility.
            class L:
                pass

            out = L()
            out.x = x
            out.y = y
            out.visibility = float(lm.visibility)
            out.presence = float(getattr(lm, "presence", 1.0))
            smoothed.append(out)

        return smoothed


class DecisionStabilizer:
    def __init__(self, confirm_frames=4, release_frames=3):
        self.confirm_frames = confirm_frames
        self.release_frames = release_frames
        self.current = None
        self.candidate = None
        self.candidate_count = 0
        self.score_ema = None

    def reset(self):
        self.current = None
        self.candidate = None
        self.candidate_count = 0
        self.score_ema = None

    def update(self, result):
        raw = result.status

        if self.score_ema is None:
            self.score_ema = float(result.score)
        else:
            self.score_ema = (
                0.28 * float(result.score)
                + 0.72 * self.score_ema
            )

        # Green is deliberately harder to enter than yellow.
        # Red needs repeated evidence, preventing one-frame jumps.
        required = self.confirm_frames

        if raw == self.current:
            self.candidate = None
            self.candidate_count = 0
        else:
            if raw != self.candidate:
                self.candidate = raw
                self.candidate_count = 1
            else:
                self.candidate_count += 1

            if self.candidate_count >= required:
                self.current = self.candidate
                self.candidate = None
                self.candidate_count = 0

        if self.current is None:
            self.current = raw

        result.status = self.current
        result.score = int(round(
            clamp(self.score_ema, 0, 100)
        ))

        return result


class TargetSmoother:
    def __init__(self, alpha=0.35):
        self.alpha = alpha
        self.previous = {}

    def reset(self):
        self.previous.clear()

    def smooth(self, targets):
        output = []

        for idx, item in enumerate(targets):
            actual, desired, label = item
            key = (label, idx)

            old = self.previous.get(key)

            if old is None:
                smoothed = desired
            else:
                smoothed = (
                    int(
                        self.alpha * desired[0]
                        + (1.0 - self.alpha) * old[0]
                    ),
                    int(
                        self.alpha * desired[1]
                        + (1.0 - self.alpha) * old[1]
                    ),
                )

            self.previous[key] = smoothed
            output.append((actual, smoothed, label))

        return output


def apply_stability(raw_result, decision_filter, target_filter):
    stable = decision_filter.update(raw_result)
    stable.targets = target_filter.smooth(stable.targets)
    return stable


# ============================================================
# REP COUNTER
# ============================================================

class RepCounter:

    def __init__(self):
        self.reps = 0
        self.stage = "START"
        self.last_rep_time = 0.0

    def reset(self):
        self.reps = 0
        self.stage = "START"
        self.last_rep_time = 0.0

    def update(self, exercise, result):
        now = time.time()

        if now - self.last_rep_time < 0.35:
            return self.reps

        value = None

        # IMPORTANT:
        # A repetition is a MOVEMENT count, not a FORM score.
        # For bicep curls we intentionally count the side-view motion
        # even when the form is red/yellow. Otherwise a bad elbow/back
        # posture makes good movement disappear from the rep counter.
        if exercise == "bicep_curls":
            value = result.angles.get("elbow")
            if value is None:
                return self.reps

            # Perspective-safe phase windows.
            # Require extension -> curl -> extension.
            EXTENDED_ANGLE = 132
            CURL_ANGLE = 105

            if self.stage == "START":
                if value >= EXTENDED_ANGLE:
                    self.stage = "DOWN"
                elif value <= CURL_ANGLE:
                    # Start curled: wait for extension before counting.
                    self.stage = "UP"

            elif self.stage == "DOWN":
                if value <= CURL_ANGLE:
                    self.stage = "UP"

            elif self.stage == "UP":
                if value >= EXTENDED_ANGLE:
                    self.reps += 1
                    self.stage = "DOWN"
                    self.last_rep_time = now

            return self.reps

        # Other exercises keep the original safety gate: only count
        # when the engine has declared a valid repetition.
        if not result.good_rep:
            return self.reps

        if exercise == "squat":
            value = result.angles.get("knee")
            if value is None:
                return self.reps

            if value >= 145:
                self.stage = "UP"

            elif (
                value <= 105
                and self.stage == "UP"
            ):
                self.stage = "DOWN"

            elif (
                value >= 145
                and self.stage == "DOWN"
            ):
                self.reps += 1
                self.stage = "UP"
                self.last_rep_time = now

        elif exercise == "lunges":
            value = result.angles.get("knee")
            if value is None:
                return self.reps

            if value >= 145:
                self.stage = "UP"

            elif (
                value <= 105
                and self.stage == "UP"
            ):
                self.stage = "DOWN"

            elif (
                value >= 145
                and self.stage == "DOWN"
            ):
                self.reps += 1
                self.stage = "UP"
                self.last_rep_time = now

        elif exercise == "push_up":
            value = result.angles.get("elbow")
            if value is None:
                return self.reps

            if value >= 150:
                self.stage = "UP"

            elif (
                value <= 100
                and self.stage == "UP"
            ):
                self.stage = "DOWN"

            elif (
                value >= 150
                and self.stage == "DOWN"
            ):
                self.reps += 1
                self.stage = "UP"
                self.last_rep_time = now

        elif exercise == "lateral_shoulder_raises":
            value = result.angles.get("raise")
            if value is None:
                return self.reps

            if value >= 65:
                self.stage = "UP"

            elif (
                value < 25
                and self.stage == "UP"
            ):
                self.reps += 1
                self.stage = "DOWN"
                self.last_rep_time = now

        elif exercise == "shoulder_press":
            value = result.angles.get("elbow")
            if value is None:
                return self.reps

            if value < 95:
                self.stage = "DOWN"

            elif (
                value > 155
                and self.stage == "DOWN"
            ):
                self.reps += 1
                self.stage = "UP"
                self.last_rep_time = now

        return self.reps



# ============================================================
# LIVE FORM INSTRUCTIONS
# ============================================================

def instruction_lines(exercise, result):
    """
    Short, human-readable coaching cues.
    These are displayed only as an additional instruction panel;
    detection, pipes, colors and rep logic remain unchanged.
    """
    if exercise == "bicep_curls":
        if result.status == "red":
            if "ELBOW" in result.message.upper():
                return [
                    "KEEP BOTH ELBOWS CLOSE",
                    "DO NOT SWING YOUR BODY",
                ]
            if "BACK" in result.message.upper() or "TORSO" in result.message.upper():
                return [
                    "KEEP BACK STRAIGHT",
                    "KEEP CHEST UP",
                ]
            return [
                "CONTROL THE MOVEMENT",
                "KEEP CHEST UP",
            ]

        if result.status == "yellow":
            return [
                "KEEP ELBOWS FIXED",
                "KEEP CHEST UP",
            ]

        return [
            "KEEP BACK STRAIGHT",
            "CHEST UP",
            "ELBOWS CLOSE TO BODY",
        ]

    if exercise == "squat":
        if result.status == "red":
            return [
                "KEEP BACK STRAIGHT",
                "CHEST UP",
                "KNEES TRACK WITH TOES",
            ]
        if result.status == "yellow":
            return [
                "CHEST UP",
                "CONTROL YOUR DEPTH",
                "KEEP KNEES ALIGNED",
            ]
        return [
            "BACK STRAIGHT",
            "CHEST UP",
            "KNEES ALIGNED",
        ]

    if exercise == "shoulder_press":
        if result.status == "red":
            return [
                "KEEP BACK STRAIGHT",
                "PRESS BOTH ARMS EVENLY",
            ]
        if result.status == "yellow":
            return [
                "KEEP CORE STABLE",
                "PRESS UP CONTROLLED",
            ]
        return [
            "BACK STRAIGHT",
            "CORE STABLE",
            "BOTH ARMS EVEN",
        ]

    if exercise == "lateral_shoulder_raises":
        if result.status == "red":
            return [
                "RAISE BOTH ARMS EVENLY",
                "DO NOT SHRUG SHOULDERS",
            ]
        if result.status == "yellow":
            return [
                "MOVE TOWARD SHOULDER HEIGHT",
                "KEEP TORSO STILL",
            ]
        return [
            "SHOULDERS RELAXED",
            "ARMS AT SHOULDER HEIGHT",
            "KEEP TORSO STILL",
        ]

    if exercise == "tricep_extension":
        return [
            "KEEP ELBOWS STABLE",
            "KEEP BACK STRAIGHT",
            "CONTROL THE EXTENSION",
        ]

    if exercise == "lunges":
        return [
            "CHEST UP",
            "BACK STRAIGHT",
            "FRONT KNEE ALIGNED",
        ]

    if exercise == "push_up":
        return [
            "KEEP BODY STRAIGHT",
            "CHEST DOWN CONTROLLED",
            "ELBOWS CONTROLLED",
        ]

    if exercise == "dumbbell_row":
        return [
            "BACK STRAIGHT",
            "CHEST STABLE",
            "PULL ELBOW BACK",
        ]

    if exercise == "sit_up":
        return [
            "KEEP MOVEMENT CONTROLLED",
            "LIFT TORSO WITH CONTROL",
        ]

    if exercise == "jumping_jack":
        return [
            "OPEN ARMS AND LEGS",
            "LAND SOFTLY",
            "KEEP MOVEMENT CONTROLLED",
        ]

    return [
        "FOLLOW THE YELLOW GUIDE",
        "KEEP YOUR FORM CONTROLLED",
    ]


def draw_instruction_panel(frame, exercise, result):
    height, width = frame.shape[:2]
    lines = instruction_lines(exercise, result)

    # Compact panel on the left side. It does not cover the
    # existing status/rep panels on the right or bottom.
    panel_w = min(360, max(300, width // 4))
    panel_h = 42 + (len(lines) * 29)

    x1 = 20
    y1 = 160
    x2 = x1 + panel_w
    y2 = min(height - 100, y1 + panel_h)

    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (x1, y1),
        (x2, y2),
        DARK,
        -1,
    )

    # Subtle transparency so the camera remains visible.
    cv2.addWeighted(
        overlay,
        0.82,
        frame,
        0.18,
        0,
        frame,
    )

    cv2.putText(
        frame,
        "FORM INSTRUCTIONS",
        (x1 + 16, y1 + 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        WHITE,
        2,
        cv2.LINE_AA,
    )

    yy = y1 + 57

    for line in lines:
        # Green instructions when form is good; yellow when
        # user is being guided; red when form is wrong.
        if result.status == "green":
            c = GREEN
        elif result.status == "yellow":
            c = YELLOW
        else:
            c = RED

        cv2.circle(
            frame,
            (x1 + 18, yy - 5),
            4,
            c,
            -1,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            line,
            (x1 + 32, yy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.39,
            WHITE,
            1,
            cv2.LINE_AA,
        )

        yy += 29


# ============================================================
# ORIGINAL SIMPLE UI - PRESERVED STYLE
# ============================================================

def draw_ui(frame, exercise, result, reps):
    height, width = frame.shape[:2]

    color = status_color(result.status)

    if result.status == "green":
        status_text = "CORRECT POSTURE"
    elif result.status == "yellow":
        status_text = "ADJUST POSITION"
    else:
        status_text = "WRONG POSTURE"

    exercise_name = EXERCISES.get(
        exercise,
        exercise.upper(),
    )

    # HEADER
    cv2.rectangle(
        frame,
        (0, 0),
        (width, 115),
        DARK,
        -1,
    )

    cv2.putText(
        frame,
        "AI GYM FORMFIT",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        WHITE,
        2,
    )

    cv2.putText(
        frame,
        exercise_name,
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        CYAN,
        2,
    )

    cv2.putText(
        frame,
        f"VIEW: {result.view}",
        (20, 98),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        WHITE,
        1,
    )

    # STATUS
    cv2.rectangle(
        frame,
        (width - 310, 18),
        (width - 20, 70),
        color,
        -1,
    )

    cv2.putText(
        frame,
        status_text,
        (width - 292, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        BLACK,
        2,
    )

    # REPS
    cv2.rectangle(
        frame,
        (width - 205, 90),
        (width - 20, 200),
        DARK,
        -1,
    )

    cv2.putText(
        frame,
        "REPS",
        (width - 165, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        WHITE,
        1,
    )

    cv2.putText(
        frame,
        str(reps),
        (width - 155, 182),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.45,
        CYAN,
        3,
    )

    # MESSAGE
    cv2.rectangle(
        frame,
        (20, height - 82),
        (width - 20, height - 18),
        DARK,
        -1,
    )

    cv2.putText(
        frame,
        result.message,
        (35, height - 43),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        color,
        2,
    )

    cv2.putText(
        frame,
        f"SCORE {result.score}%",
        (width - 170, height - 43),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        WHITE,
        1,
    )

    cv2.putText(
        frame,
        "STABLE AI CHECK",
        (width - 310, 98),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.32,
        GREEN,
        1,
    )

    # LEGEND
    cv2.putText(
        frame,
        "GREEN = CORRECT",
        (20, 135),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        GREEN,
        1,
    )

    cv2.putText(
        frame,
        "RED = WRONG",
        (190, 135),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        RED,
        1,
    )

    cv2.putText(
        frame,
        "YELLOW DOTTED = MOVE HERE",
        (330, 135),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        YELLOW,
        1,
    )


# ============================================================
# CAMERA
# ============================================================

def run_camera(exercise):
    exercise = normalize_exercise(exercise)

    if exercise not in EXERCISES:
        print("Invalid exercise.")
        print("Available:")
        for key, name in EXERCISES.items():
            print("-", key, "=>", name)
        return

    print()
    print("=" * 60)
    print("AI GYM FORMFIT - STRONG FORM CHECK")
    print("=" * 60)
    print("Exercise:", EXERCISES[exercise])
    print("Q = Exit | R = Reset")
    print("=" * 60)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Camera not available.")
        return

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280,
    )
    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720,
    )
    cap.set(
        cv2.CAP_PROP_FPS,
        30,
    )

    counter = RepCounter()
    landmark_filter = LandmarkSmoother(alpha=0.42)
    decision_filter = DecisionStabilizer(
        confirm_frames=4,
        release_frames=3,
    )
    target_filter = TargetSmoother(alpha=0.35)

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        smooth_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.72,
        min_tracking_confidence=0.72,
    ) as pose:

        while True:
            success, frame = cap.read()

            if not success:
                break

            frame = cv2.flip(frame, 1)

            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            results = pose.process(rgb)

            if results.pose_landmarks:
                raw_landmarks = results.pose_landmarks.landmark

                # Smooth camera jitter BEFORE calculating angles.
                landmarks = landmark_filter.update(
                    raw_landmarks
                )

                raw_result = analyze_exercise(
                    exercise,
                    landmarks,
                    width,
                    height,
                )

                # Stabilize the visible form state and score.
                result = apply_stability(
                    raw_result,
                    decision_filter,
                    target_filter,
                )

                reps = counter.update(
                    exercise,
                    result,
                )

                # Faint base skeleton.
                mp_draw.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_draw.DrawingSpec(
                        color=GRAY,
                        thickness=1,
                        circle_radius=2,
                    ),
                    mp_draw.DrawingSpec(
                        color=GRAY,
                        thickness=1,
                    ),
                )

                # Form pipes.
                for a, b, status in result.pipes:
                    draw_pipe(
                        frame,
                        a,
                        b,
                        status_color(status),
                        6,
                    )

                # Yellow correction targets.
                draw_correction_guides(
                    frame,
                    result,
                )

                draw_ui(
                    frame,
                    exercise,
                    result,
                    reps,
                )

                # NEW: live coaching cues. Existing UI, pipes,
                # colors, correction guides and rep logic unchanged.
                draw_instruction_panel(
                    frame,
                    exercise,
                    result,
                )

            else:
                cv2.putText(
                    frame,
                    "BODY NOT DETECTED",
                    (25, 55),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    RED,
                    3,
                )

                cv2.putText(
                    frame,
                    "MOVE INTO CAMERA VIEW",
                    (25, 95),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.50,
                    WHITE,
                    2,
                )

            cv2.imshow(
                "AI Gym FormFit",
                frame,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                break

            if key == ord("r"):
                counter.reset()
                landmark_filter.reset()
                decision_filter.reset()
                target_filter.reset()

            if key == ord("1"):
                exercise = "bicep_curls"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("2"):
                exercise = "squat"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("3"):
                exercise = "shoulder_press"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("4"):
                exercise = "lateral_shoulder_raises"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("5"):
                exercise = "tricep_extension"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("6"):
                exercise = "lunges"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("7"):
                exercise = "push_up"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("8"):
                exercise = "dumbbell_row"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("9"):
                exercise = "sit_up"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

            elif key == ord("0"):
                exercise = "jumping_jack"
                counter.reset()
                decision_filter.reset()
                target_filter.reset()

    cap.release()
    cv2.destroyAllWindows()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("AI GYM FORMFIT - STRONG FORM CHECK")
    print("=" * 60)
    print()

    for key, name in EXERCISES.items():
        print("-", name)

    print()
    exercise = input("Enter exercise: ")

    run_camera(exercise)
