
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
    "bench_press": "BENCH PRESS",
    "deadlift": "DEADLIFT",
    "front_raise": "FRONT RAISE",
    "hammer_curl": "HAMMER CURL",
    "calf_raise": "CALF RAISE",
    "glute_bridge": "GLUTE BRIDGE",
    "plank": "PLANK",
    "mountain_climber": "MOUNTAIN CLIMBER",
    "burpee": "BURPEE",
    "step_up": "STEP-UP",
    "reverse_lunge": "REVERSE LUNGE",
    "chest_fly": "CHEST FLY",
    "incline_dumbbell_press": "INCLINE DUMBBELL PRESS",
    "decline_bench_press": "DECLINE BENCH PRESS",
    "incline_bench_press": "INCLINE BENCH PRESS",
    "dumbbell_bench_press": "DUMBBELL BENCH PRESS",
    "close_grip_bench_press": "CLOSE GRIP BENCH PRESS",
    "push_up_wide_grip": "WIDE GRIP PUSH-UP",
    "push_up_diamond": "DIAMOND PUSH-UP",
    "incline_push_up": "INCLINE PUSH-UP",
    "decline_push_up": "DECLINE PUSH-UP",
    "chest_press_machine": "CHEST PRESS MACHINE",
    "cable_crossover": "CABLE CROSSOVER",
    "low_cable_crossover": "LOW CABLE CROSSOVER",
    "lat_pulldown": "LAT PULLDOWN",
    "close_grip_lat_pulldown": "CLOSE GRIP LAT PULLDOWN",
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
    "lat pulldown": "lat_pulldown",
    "lat pulldowns": "lat_pulldown",
    "close grip lat pulldown": "close_grip_lat_pulldown",
    "close-grip lat pulldown": "close_grip_lat_pulldown",
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

        if elbow_bad_count == 2:
            pipes[1] = (pipes[1][0], pipes[1][1], "red")
            pipes[3] = (pipes[3][0], pipes[3][1], "red")

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
        pipes = [(a, b, "red") for a, b, _ in pipes]
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
        pipes = [(a, b, "red") for a, b, _ in pipes]
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

    arm_span = abs(lw[0] - rw[0]) / shoulder_width

    return FormResult(
        status,
        message,
        98 if arms_open else 75,
        {"arm_span": arm_span},
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
# EXPANDED EXERCISE RULES — BATCH 1
# ============================================================
#
# These rules are added as separate exercise-specific branches.
# Existing 10 exercises remain untouched.
# ============================================================

def _side_triplet_visible(landmarks, ids):
    return all(visible(landmarks, i) for i in ids)


def _best_side_triplet(landmarks, triplets):
    best = None
    score_best = -1.0
    for triplet in triplets:
        score = sum(float(landmarks[i].visibility) for i in triplet)
        if score > score_best:
            score_best = score
            best = triplet
    return best


def analyze_bench_press(landmarks, width, height):
    ids = [
        (LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST),
        (RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST),
    ]
    if not all(_side_triplet_visible(landmarks, x) for x in ids):
        return FormResult("red", "SHOW BOTH ARMS CLEARLY", 0, view="FRONT")

    values = []
    pipes = []
    bad_sym = False
    for (sid, eid, wid) in ids:
        s = xy(landmarks, sid, width, height)
        e = xy(landmarks, eid, width, height)
        w = xy(landmarks, wid, width, height)
        a = angle(s, e, w)
        values.append(a)
        pipes.extend([(s, e, "green"), (e, w, "green")])

    bad_sym = abs(values[0] - values[1]) > 18
    good_range = all(70 <= v <= 160 for v in values)

    if bad_sym:
        pipes = [(a, b, "red") for a, b, _ in pipes]
        return FormResult(
            "red", "PRESS BOTH ARMS EVENLY", 55,
            {"elbow": sum(values)/2}, pipes, [], "FRONT", False
        )
    if not good_range:
        return FormResult(
            "yellow", "CONTROL THE PRESS RANGE", 78,
            {"elbow": sum(values)/2}, pipes, [], "FRONT", False
        )
    return FormResult(
        "green", "BENCH PRESS FORM GOOD", 96,
        {"elbow": sum(values)/2}, pipes, [], "FRONT", True
    )


def analyze_deadlift(landmarks, width, height):
    side = choose_side(landmarks)
    if side == "LEFT":
        hid, kid, aid, sid = LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, LEFT_SHOULDER
    else:
        hid, kid, aid, sid = RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, RIGHT_SHOULDER

    if not all(visible(landmarks, i) for i in (hid, kid, aid, sid)):
        return FormResult("red", "SHOW FULL BODY FROM SIDE", 0, view="SIDE")

    h = xy(landmarks, hid, width, height)
    k = xy(landmarks, kid, width, height)
    a = xy(landmarks, aid, width, height)
    s = xy(landmarks, sid, width, height)

    knee = angle(h, k, a)
    back = vertical_angle(s, h)

    pipes=[(s,h,"green"),(h,k,"green"),(k,a,"green")]
    targets=[]

    if back > 48:
        pipes[0]=(s,h,"red")
        targets.append((s,(h[0], max(0,h[1]-distance(s,h))),"KEEP BACK NEUTRAL"))
        return FormResult("red","KEEP BACK NEUTRAL",52,{"knee":knee,"back":back},pipes,targets,"SIDE",False)

    if knee < 105:
        return FormResult("yellow","HINGE MORE — DON'T SQUAT",72,{"knee":knee,"back":back},pipes,targets,"SIDE",False)

    return FormResult("green","DEADLIFT FORM GOOD",96,{"knee":knee,"back":back},pipes,targets,"SIDE",True)


def analyze_front_raise(landmarks, width, height):
    pairs=[(LEFT_SHOULDER,LEFT_WRIST),(RIGHT_SHOULDER,RIGHT_WRIST)]
    if not all(visible(landmarks,a) and visible(landmarks,b) for a,b in pairs):
        return FormResult("red","SHOW BOTH ARMS",0,view="FRONT")

    vals=[]
    pipes=[]
    for sid,wid in pairs:
        s=xy(landmarks,sid,width,height); w=xy(landmarks,wid,width,height)
        vals.append(vertical_angle(s,w))
        pipes.append((s,w,"green"))

    avg=sum(vals)/2
    symmetry=abs(vals[0]-vals[1])<=15

    if not symmetry:
        pipes = [(a, b, "red") for a, b, _ in pipes]
        return FormResult("red","RAISE BOTH ARMS EVENLY",55,{"raise":avg},pipes,[],"FRONT",False)
    if avg < 55:
        return FormResult("yellow","RAISE TOWARD SHOULDER HEIGHT",75,{"raise":avg},pipes,[],"FRONT",False)
    if avg > 105:
        return FormResult("yellow","DO NOT OVER-RAISE",78,{"raise":avg},pipes,[],"FRONT",False)

    return FormResult("green","FRONT RAISE FORM GOOD",96,{"raise":avg},pipes,[],"FRONT",True)


def analyze_hammer_curl(landmarks, width, height):
    result=analyze_bicep(landmarks,width,height)
    result.message = (
        "HAMMER CURL FORM GOOD"
        if result.status=="green"
        else ("KEEP ELBOWS FIXED" if result.status=="yellow" else "KEEP ELBOWS FIXED")
    )
    return result


def analyze_calf_raise(landmarks, width, height):
    pairs=[(LEFT_KNEE,LEFT_ANKLE),(RIGHT_KNEE,RIGHT_ANKLE)]
    if not all(visible(landmarks,a) and visible(landmarks,b) for a,b in pairs):
        return FormResult("red","SHOW BOTH LEGS",0,view="FRONT")

    k1,a1=xy(landmarks,*pairs[0][0:1],width,height),xy(landmarks,*pairs[0][1:2],width,height)
    k2,a2=xy(landmarks,*pairs[1][0:1],width,height),xy(landmarks,*pairs[1][1:2],width,height)

    knee_y_diff=abs(k1[1]-k2[1])
    ankle_dx=abs(a1[0]-a2[0])
    scale=max(distance(k1,k2),1)

    pipes=[(k1,a1,"green"),(k2,a2,"green")]
    if knee_y_diff>0.30*scale:
        return FormResult("yellow","KEEP KNEES STABLE",75,{"calf":ankle_dx},pipes,[],"FRONT",False)
    if ankle_dx<0.10*max(width,1):
        return FormResult("green","CALF RAISE FORM GOOD",95,{"calf":ankle_dx},pipes,[],"FRONT",True)
    return FormResult("yellow","KEEP BOTH SIDES EVEN",78,{"calf":ankle_dx},pipes,[],"FRONT",False)


def analyze_glute_bridge(landmarks, width, height):
    side=choose_side(landmarks)
    if side=="LEFT":
        sid,hid,kid=LEFT_SHOULDER,LEFT_HIP,LEFT_KNEE
    else:
        sid,hid,kid=RIGHT_SHOULDER,RIGHT_HIP,RIGHT_KNEE

    if not all(visible(landmarks,i) for i in (sid,hid,kid)):
        return FormResult("red","SHOW SHOULDER, HIP AND KNEE",0,view="SIDE")

    s=xy(landmarks,sid,width,height); h=xy(landmarks,hid,width,height); k=xy(landmarks,kid,width,height)
    hip=angle(s,h,k)
    pipes=[(s,h,"green"),(h,k,"green")]

    if hip < 145:
        return FormResult("yellow","EXTEND HIPS WITHOUT ARCHING",75,{"hip":hip},pipes,[],"SIDE",False)
    return FormResult("green","GLUTE BRIDGE FORM GOOD",96,{"hip":hip},pipes,[],"SIDE",True)


def analyze_plank(landmarks, width, height):
    side=choose_side(landmarks)
    if side=="LEFT":
        sid,hid,aid=LEFT_SHOULDER,LEFT_HIP,LEFT_ANKLE
    else:
        sid,hid,aid=RIGHT_SHOULDER,RIGHT_HIP,RIGHT_ANKLE

    if not all(visible(landmarks,i) for i in (sid,hid,aid)):
        return FormResult("red","SHOW FULL SIDE BODY",0,view="SIDE")

    s=xy(landmarks,sid,width,height); h=xy(landmarks,hid,width,height); a=xy(landmarks,aid,width,height)
    line=angle(s,h,a)
    pipes=[(s,h,"green"),(h,a,"green")]

    if line < 165:
        return FormResult("red","KEEP BODY IN A STRAIGHT LINE",50,{"body_line":line},pipes,[],"SIDE",False)
    return FormResult("green","PLANK FORM GOOD",98,{"body_line":line},pipes,[],"SIDE",True)


def analyze_mountain_climber(landmarks, width, height):
    side=choose_side(landmarks)
    if side=="LEFT":
        sid,hid,kid,aid=LEFT_SHOULDER,LEFT_HIP,LEFT_KNEE,LEFT_ANKLE
    else:
        sid,hid,kid,aid=RIGHT_SHOULDER,RIGHT_HIP,RIGHT_KNEE,RIGHT_ANKLE
    if not all(visible(landmarks,i) for i in (sid,hid,kid,aid)):
        return FormResult("red","SHOW BODY CLEARLY",0,view="SIDE")
    s=xy(landmarks,sid,width,height); h=xy(landmarks,hid,width,height); k=xy(landmarks,kid,width,height); a=xy(landmarks,aid,width,height)
    line=angle(s,h,a)
    knee=angle(h,k,a)
    pipes=[(s,h,"green"),(h,k,"green"),(k,a,"green")]
    if line < 155:
        return FormResult("red","KEEP HIPS CONTROLLED",50,{"body_line":line,"knee_drive":knee},pipes,[],"SIDE",False)
    return FormResult("green" if knee is not None else "yellow","MOUNTAIN CLIMBER FORM GOOD",92,{"body_line":line,"knee_drive":knee},pipes,[],"SIDE",True)


def analyze_burpee(landmarks, width, height):
    side=choose_side(landmarks)
    if side=="LEFT":
        sid,hid,kid,aid=LEFT_SHOULDER,LEFT_HIP,LEFT_KNEE,LEFT_ANKLE
    else:
        sid,hid,kid,aid=RIGHT_SHOULDER,RIGHT_HIP,RIGHT_KNEE,RIGHT_ANKLE
    if not all(visible(landmarks,i) for i in (sid,hid,kid,aid)):
        return FormResult("red","SHOW FULL BODY",0,view="SIDE")
    s=xy(landmarks,sid,width,height); h=xy(landmarks,hid,width,height); k=xy(landmarks,kid,width,height); a=xy(landmarks,aid,width,height)
    back=vertical_angle(s,h)
    knee=angle(h,k,a)
    pipes=[(s,h,"green"),(h,k,"green"),(k,a,"green")]
    if back>55:
        pipes[0]=(s,h,"red")
        return FormResult("red","KEEP BACK CONTROLLED",52,{"back":back,"knee":knee},pipes,[],"SIDE",False)
    return FormResult("green","BURPEE FORM GOOD",92,{"back":back,"knee":knee},pipes,[],"SIDE",True)


def analyze_step_up(landmarks, width, height):
    side=choose_side(landmarks)
    if side=="LEFT":
        hid,kid,aid=LEFT_HIP,LEFT_KNEE,LEFT_ANKLE
    else:
        hid,kid,aid=RIGHT_HIP,RIGHT_KNEE,RIGHT_ANKLE
    if not all(visible(landmarks,i) for i in (hid,kid,aid)):
        return FormResult("red","SHOW FULL LEG",0,view="SIDE")
    h=xy(landmarks,hid,width,height); k=xy(landmarks,kid,width,height); a=xy(landmarks,aid,width,height)
    knee=angle(h,k,a)
    pipes=[(h,k,"green"),(k,a,"green")]
    if k[0]-a[0] > 0.55*max(distance(k,a),1):
        return FormResult("red","KEEP KNEE ALIGNED",55,{"knee":knee},pipes,[],"SIDE",False)
    return FormResult("green","STEP-UP FORM GOOD",95,{"knee":knee},pipes,[],"SIDE",True)


def analyze_reverse_lunge(landmarks, width, height):
    result=analyze_lunge(landmarks,width,height)
    if result.status=="green":
        result.message="REVERSE LUNGE FORM GOOD"
    return result


def analyze_chest_fly(landmarks, width, height):
    ids=[(LEFT_SHOULDER,LEFT_ELBOW,LEFT_WRIST),(RIGHT_SHOULDER,RIGHT_ELBOW,RIGHT_WRIST)]
    if not all(_side_triplet_visible(landmarks,x) for x in ids):
        return FormResult("red","SHOW BOTH ARMS",0,view="FRONT")
    vals=[]; pipes=[]
    for sid,eid,wid in ids:
        s=xy(landmarks,sid,width,height); e=xy(landmarks,eid,width,height); w=xy(landmarks,wid,width,height)
        vals.append(angle(s,e,w)); pipes.extend([(s,e,"green"),(e,w,"green")])
    symmetry=abs(vals[0]-vals[1])<=20
    if not symmetry:
        return FormResult("red","OPEN AND CLOSE BOTH ARMS EVENLY",55,{"elbow":sum(vals)/2},pipes,[],"FRONT",False)
    return FormResult("green","CHEST FLY FORM GOOD",94,{"elbow":sum(vals)/2},pipes,[],"FRONT",True)



# ============================================================
# EXPANDED EXERCISE RULES — BATCH 2
# ============================================================
# Chest + push family. Existing analyzers remain untouched.
# Variations reuse the validated movement geometry while exposing
# exercise-specific feedback and keeping distinct exercise IDs.
# ============================================================

def _rename_result(result, good_message, yellow_message=None, red_message=None):
    if result.status == "green":
        result.message = good_message
    elif result.status == "yellow" and yellow_message:
        result.message = yellow_message
    elif result.status == "red" and red_message:
        result.message = red_message
    return result


def analyze_incline_dumbbell_press(landmarks, width, height):
    return _rename_result(
        analyze_bench_press(landmarks, width, height),
        "INCLINE DUMBBELL PRESS FORM GOOD",
        "CONTROL THE PRESS RANGE",
        "KEEP BOTH ARMS EVEN",
    )


def analyze_decline_bench_press(landmarks, width, height):
    return _rename_result(
        analyze_bench_press(landmarks, width, height),
        "DECLINE BENCH PRESS FORM GOOD",
        "CONTROL THE PRESS RANGE",
        "KEEP BOTH ARMS EVEN",
    )


def analyze_incline_bench_press(landmarks, width, height):
    return _rename_result(
        analyze_bench_press(landmarks, width, height),
        "INCLINE BENCH PRESS FORM GOOD",
        "CONTROL THE PRESS RANGE",
        "KEEP BOTH ARMS EVEN",
    )


def analyze_dumbbell_bench_press(landmarks, width, height):
    return _rename_result(
        analyze_bench_press(landmarks, width, height),
        "DUMBBELL BENCH PRESS FORM GOOD",
        "CONTROL BOTH DUMBBELLS EVENLY",
        "KEEP BOTH ARMS EVEN",
    )


def analyze_close_grip_bench_press(landmarks, width, height):
    return _rename_result(
        analyze_bench_press(landmarks, width, height),
        "CLOSE-GRIP PRESS FORM GOOD",
        "KEEP ELBOWS CONTROLLED",
        "KEEP ELBOWS TUCKED",
    )


def analyze_push_up_wide_grip(landmarks, width, height):
    return _rename_result(
        analyze_pushup(landmarks, width, height),
        "WIDE PUSH-UP FORM GOOD",
        "CONTROL CHEST DESCENT",
        "KEEP BODY STRAIGHT",
    )


def analyze_push_up_diamond(landmarks, width, height):
    return _rename_result(
        analyze_pushup(landmarks, width, height),
        "DIAMOND PUSH-UP FORM GOOD",
        "KEEP ELBOWS CONTROLLED",
        "KEEP BODY STRAIGHT",
    )


def analyze_incline_push_up(landmarks, width, height):
    return _rename_result(
        analyze_pushup(landmarks, width, height),
        "INCLINE PUSH-UP FORM GOOD",
        "CONTROL CHEST DESCENT",
        "KEEP BODY STRAIGHT",
    )


def analyze_decline_push_up(landmarks, width, height):
    return _rename_result(
        analyze_pushup(landmarks, width, height),
        "DECLINE PUSH-UP FORM GOOD",
        "CONTROL DESCENT",
        "KEEP BODY STRAIGHT",
    )


def analyze_chest_press_machine(landmarks, width, height):
    return _rename_result(
        analyze_bench_press(landmarks, width, height),
        "MACHINE CHEST PRESS FORM GOOD",
        "PRESS WITH CONTROL",
        "KEEP BOTH ARMS EVEN",
    )


def analyze_cable_crossover(landmarks, width, height):
    return analyze_cable_fly_pattern(landmarks, width, height, low=False)


def analyze_low_cable_crossover(landmarks, width, height):
    return analyze_cable_fly_pattern(landmarks, width, height, low=True)



# ============================================================
# REP-SIGNAL REFINEMENTS
# ============================================================
# These override only the signal emitted to RepCounter.
# Form status/pipes remain the same architecture.

def analyze_calf_raise(landmarks, width, height):
    pairs = [(LEFT_KNEE, LEFT_ANKLE, "LEFT"), (RIGHT_KNEE, RIGHT_ANKLE, "RIGHT")]
    if not all(visible(landmarks, a) and visible(landmarks, b) for a,b,_ in pairs):
        return FormResult("red", "SHOW BOTH LEGS", 0, view="FRONT")

    pipes = []
    signals = []
    for kid, aid, _ in pairs:
        k = xy(landmarks, kid, width, height)
        a = xy(landmarks, aid, width, height)
        seg = max(distance(k, a), 1.0)
        # Heel raise signal: vertical gap from knee toward ankle.
        calf_signal = (k[1] - a[1]) / seg
        signals.append(calf_signal)
        pipes.append((k, a, "green"))

    value = sum(signals) / 2.0
    symmetry = abs(signals[0] - signals[1]) <= 0.18

    if not symmetry:
        return FormResult("red", "KEEP BOTH SIDES EVEN", 55, {"calf": value}, pipes, [], "FRONT", False)
    if value >= 1.10:
        return FormResult("green", "CALF RAISE FORM GOOD", 96, {"calf": value}, pipes, [], "FRONT", True)
    return FormResult("yellow", "RAISE YOUR HEELS HIGHER", 76, {"calf": value}, pipes, [], "FRONT", False)


def analyze_mountain_climber(landmarks, width, height):
    side_values = []
    pipes = []

    for sid, hid, kid, aid in (
        (LEFT_SHOULDER, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE),
        (RIGHT_SHOULDER, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE),
    ):
        if not all(visible(landmarks, i) for i in (sid, hid, kid, aid)):
            continue
        s = xy(landmarks, sid, width, height)
        h = xy(landmarks, hid, width, height)
        k = xy(landmarks, kid, width, height)
        a = xy(landmarks, aid, width, height)
        body = angle(s, h, a)
        knee = angle(h, k, a)
        if body is not None and knee is not None:
            side_values.append((body, knee))
        pipes.extend([(s, h, "green"), (h, k, "green"), (k, a, "green")])

    if len(side_values) < 1:
        return FormResult("red", "SHOW BODY CLEARLY", 0, view="SIDE")

    body_values = [x[0] for x in side_values]
    knee_values = [x[1] for x in side_values]
    body_line = min(body_values)
    knee_drive = min(knee_values)

    if body_line < 155:
        return FormResult("red", "KEEP HIPS CONTROLLED", 52, {"body_line": body_line, "knee_drive": knee_drive}, pipes, [], "SIDE", False)

    if knee_drive <= 95:
        return FormResult("green", "MOUNTAIN CLIMBER FORM GOOD", 94, {"body_line": body_line, "knee_drive": knee_drive}, pipes, [], "SIDE", True)

    return FormResult("yellow", "DRIVE KNEE FORWARD WITH CONTROL", 78, {"body_line": body_line, "knee_drive": knee_drive}, pipes, [], "SIDE", False)


def analyze_chest_fly(landmarks, width, height):
    pairs = [(LEFT_SHOULDER, LEFT_WRIST), (RIGHT_SHOULDER, RIGHT_WRIST)]
    if not all(visible(landmarks, a) and visible(landmarks, b) for a,b in pairs):
        return FormResult("red", "SHOW BOTH ARMS", 0, view="FRONT")

    points = []
    pipes = []
    for sid, wid in pairs:
        s = xy(landmarks, sid, width, height)
        w = xy(landmarks, wid, width, height)
        points.extend([s, w])
        pipes.append((s, w, "green"))

    ls, rs = points[0], points[2]
    lw, rw = points[1], points[3]
    shoulder_width = max(distance(ls, rs), 1.0)
    fly_signal = distance(lw, rw) / shoulder_width

    if fly_signal <= 0.45:
        status, message, score = "green", "CHEST FLY FORM GOOD", 95
    elif fly_signal <= 1.10:
        status, message, score = "yellow", "CONTROL THE FLY RANGE", 78
    else:
        status, message, score = "yellow", "CONTROL THE OPEN POSITION", 76

    return FormResult(
        status,
        message,
        score,
        {"fly": fly_signal},
        pipes,
        [],
        "FRONT",
        status == "green",
    )



def _analyze_lat_pulldown_core(landmarks, width, height):
    """Exercise-specific lat-pulldown rule.

    Uses shoulder/elbow/wrist geometry and torso stability. It deliberately
    does not reuse the row, curl, press, or lateral-raise analyzers because
    those movement patterns can incorrectly reject a pulldown.
    """
    pairs = [
        (LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST),
        (RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST),
    ]
    if not all(all(visible(landmarks, i, 0.45) for i in p) for p in pairs):
        return FormResult("red", "SHOW BOTH ARMS CLEARLY", 0, view="FRONT")

    ls = xy(landmarks, LEFT_SHOULDER, width, height)
    rs = xy(landmarks, RIGHT_SHOULDER, width, height)
    lh = xy(landmarks, LEFT_HIP, width, height) if visible(landmarks, LEFT_HIP, 0.40) else None
    rh = xy(landmarks, RIGHT_HIP, width, height) if visible(landmarks, RIGHT_HIP, 0.40) else None

    elbows = []
    wrists = []
    elbow_angles = []
    pipes = []
    for sid, eid, wid in pairs:
        s = xy(landmarks, sid, width, height)
        ept = xy(landmarks, eid, width, height)
        wpt = xy(landmarks, wid, width, height)
        elbows.append(ept); wrists.append(wpt)
        elbow_angles.append(angle(s, ept, wpt))
        pipes.extend([(s, ept, "green"), (ept, wpt, "green")])

    shoulder_scale = max(distance(ls, rs), 1.0)
    symmetry = abs(elbows[0][1] - elbows[1][1]) <= 0.18 * shoulder_scale

    torso_lean = None
    if lh is not None and rh is not None:
        torso_lean = (abs((ls[0] + rs[0]) / 2 - (lh[0] + rh[0]) / 2)
                      / max(abs(((ls[1] + rs[1]) / 2 - (lh[1] + rh[1]) / 2)), 1))
        torso_lean = math.degrees(math.atan(torso_lean))

    avg_elbow = sum(elbow_angles) / 2.0
    avg_elbow_drop = ((ls[1] + rs[1]) / 2) - ((elbows[0][1] + elbows[1][1]) / 2)
    drop_ratio = avg_elbow_drop / shoulder_scale

    if torso_lean is not None and torso_lean > 28:
        pipes = [(a, b, "red") if a in (ls, rs) else (a, b, s) for a, b, s in pipes]
        return FormResult("red", "KEEP TORSO CONTROLLED", 55,
                          {"elbow": avg_elbow, "elbow_drop": drop_ratio, "torso": torso_lean},
                          pipes, [], "FRONT", False)

    if not symmetry:
        pipes = [(a, b, "red") for a, b, _ in pipes]
        return FormResult("red", "PULL BOTH ELBOWS EVENLY", 55,
                          {"elbow": avg_elbow, "elbow_drop": drop_ratio, "torso": torso_lean},
                          pipes, [], "FRONT", False)

    # Top position: arms extended overhead. Bottom position: elbows have
    # descended below the shoulder line while remaining controlled.
    if avg_elbow <= 95 and drop_ratio >= 0.08:
        return FormResult("green", "LAT PULLDOWN FORM GOOD", 96,
                          {"elbow": avg_elbow, "elbow_drop": drop_ratio, "torso": torso_lean},
                          pipes, [], "FRONT", True)

    if avg_elbow >= 145 and drop_ratio <= -0.02:
        return FormResult("green", "LAT PULLDOWN START POSITION GOOD", 94,
                          {"elbow": avg_elbow, "elbow_drop": drop_ratio, "torso": torso_lean},
                          pipes, [], "FRONT", True)

    return FormResult("yellow", "DRIVE ELBOWS DOWN WITH CONTROL", 78,
                      {"elbow": avg_elbow, "elbow_drop": drop_ratio, "torso": torso_lean},
                      pipes, [], "FRONT", False)


def analyze_lat_pulldown(landmarks, width, height):
    return _analyze_lat_pulldown_core(landmarks, width, height)


def analyze_close_grip_lat_pulldown(landmarks, width, height):
    result = _analyze_lat_pulldown_core(landmarks, width, height)
    if result.status == "green":
        result.message = "CLOSE GRIP LAT PULLDOWN FORM GOOD"
    elif result.status == "yellow":
        result.message = "KEEP ELBOWS TRACKING DOWN"
    return result


def analyze_cable_fly_pattern(landmarks, width, height, low=False):
    pairs = [
        (LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST),
        (RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST),
    ]
    if not all(all(visible(landmarks, i, 0.45) for i in p) for p in pairs):
        return FormResult("red", "SHOW BOTH ARMS", 0, view="FRONT")

    ls = xy(landmarks, LEFT_SHOULDER, width, height)
    rs = xy(landmarks, RIGHT_SHOULDER, width, height)
    lw = xy(landmarks, LEFT_WRIST, width, height)
    rw = xy(landmarks, RIGHT_WRIST, width, height)
    le = xy(landmarks, LEFT_ELBOW, width, height)
    re = xy(landmarks, RIGHT_ELBOW, width, height)
    shoulder_width = max(distance(ls, rs), 1.0)
    fly = distance(lw, rw) / shoulder_width
    elbow_angles = [angle(ls, le, lw), angle(rs, re, rw)]
    pipes = [(ls, le, "green"), (le, lw, "green"), (rs, re, "green"), (re, rw, "green")]
    symmetry = abs(elbow_angles[0] - elbow_angles[1]) <= 20
    if not symmetry:
        return FormResult("red", "KEEP BOTH ARMS EVEN", 55, {"fly": fly},
                          [(a,b,"red") for a,b,_ in pipes], [], "FRONT", False)
    if 0.30 <= fly <= 0.75:
        return FormResult("green", "CABLE CROSSOVER FORM GOOD" if not low else "LOW CABLE CROSSOVER FORM GOOD",
                          95, {"fly": fly}, pipes, [], "FRONT", True)
    if fly <= 1.25:
        return FormResult("yellow", "CONTROL THE CABLE PATH", 78, {"fly": fly}, pipes, [], "FRONT", False)
    return FormResult("yellow", "BRING HANDS TOGETHER WITH CONTROL", 76, {"fly": fly}, pipes, [], "FRONT", False)


# ============================================================
# DISPATCH
# ============================================================


def add_professional_pipes(result, landmarks, width, height):
    """Add a complete bilateral pose skeleton without changing form rules.

    Existing exercise-specific pipes keep their original status. Missing
    anatomical segments are added as green structural pipes. Low-confidence
    landmarks are skipped so the skeleton does not jump to bad coordinates.
    """
    # MediaPipe Pose landmark indices.
    NOSE = 0
    LEFT_EAR = 7
    RIGHT_EAR = 8
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT = 31
    RIGHT_FOOT = 32

    # Use the engine's own visibility function and a slightly permissive
    # threshold for the structural overlay. Form decisions remain unchanged.
    def ok(i):
        try:
            return visible(landmarks, i, threshold=0.35)
        except TypeError:
            return visible(landmarks, i)

    def point(i):
        return xy(landmarks, i, width, height)

    # Existing segments are compared geometrically so we never draw a green
    # duplicate on top of an exercise-specific red/yellow pipe.
    existing = []
    for a, b, status in result.pipes:
        existing.append((a, b, status))

    def same_point(p, q, tolerance=8):
        return distance(p, q) <= tolerance

    def same_segment(a, b, x, y):
        return (
            same_point(a, x) and same_point(b, y)
        ) or (
            same_point(a, y) and same_point(b, x)
        )

    def already_drawn(a, b):
        return any(
            same_segment(a, b, x, y)
            for x, y, _ in existing
        )

    def add_structural(aid, bid):
        if not (ok(aid) and ok(bid)):
            return
        a = point(aid)
        b = point(bid)
        if not already_drawn(a, b):
            result.pipes.append((a, b, "green"))
            existing.append((a, b, "green"))

    # Core bilateral skeleton.
    segments = [
        # Head / neck / shoulders
        (NOSE, LEFT_EAR),
        (NOSE, RIGHT_EAR),
        (LEFT_SHOULDER, RIGHT_SHOULDER),
        (LEFT_SHOULDER, LEFT_HIP),
        (RIGHT_SHOULDER, RIGHT_HIP),
        (LEFT_HIP, RIGHT_HIP),

        # Left arm
        (LEFT_SHOULDER, LEFT_ELBOW),
        (LEFT_ELBOW, LEFT_WRIST),

        # Right arm
        (RIGHT_SHOULDER, RIGHT_ELBOW),
        (RIGHT_ELBOW, RIGHT_WRIST),

        # Left leg
        (LEFT_HIP, LEFT_KNEE),
        (LEFT_KNEE, LEFT_ANKLE),
        (LEFT_ANKLE, LEFT_HEEL),
        (LEFT_ANKLE, LEFT_FOOT),

        # Right leg
        (RIGHT_HIP, RIGHT_KNEE),
        (RIGHT_KNEE, RIGHT_ANKLE),
        (RIGHT_ANKLE, RIGHT_HEEL),
        (RIGHT_ANKLE, RIGHT_FOOT),
    ]

    for a, b in segments:
        add_structural(a, b)

    # Keep the exercise's existing correction pipes at the end of the list
    # so yellow/red guidance stays visually dominant in renderers that draw
    # pipes sequentially.




def analyze_exercise(exercise, landmarks, width, height):
    def finish(result):
        add_professional_pipes(result, landmarks, width, height)

        # Bilateral leg red is ONLY applied if BOTH visible legs independently
        # violate the same existing knee/ankle alignment rule.
        if exercise in {"squat", "lunges", "reverse_lunge", "step_up"}:
            ids = (
                LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
                RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE,
            )
            if all(visible(landmarks, i, 0.50) for i in ids):
                fails = []
                for h_id, k_id, a_id in (
                    (LEFT_HIP, LEFT_KNEE, LEFT_ANKLE),
                    (RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE),
                ):
                    h = xy(landmarks, h_id, width, height)
                    k = xy(landmarks, k_id, width, height)
                    a = xy(landmarks, a_id, width, height)
                    leg = max(distance(k, a), 1.0)
                    fails.append(abs(k[0] - a[0]) / leg > 0.70)

                if all(fails):
                    leg_ids = {
                        (LEFT_HIP, LEFT_KNEE),
                        (LEFT_KNEE, LEFT_ANKLE),
                        (RIGHT_HIP, RIGHT_KNEE),
                        (RIGHT_KNEE, RIGHT_ANKLE),
                    }

                    def same_seg(a, b, x, y, tol=18):
                        return (
                            distance(a, x) <= tol and distance(b, y) <= tol
                        ) or (
                            distance(a, y) <= tol and distance(b, x) <= tol
                        )

                    updated = []
                    for pipe in result.pipes:
                        a, b, status = pipe[:3]
                        extra = tuple(pipe[3:])
                        red = False
                        for ia, ib in leg_ids:
                            x = xy(landmarks, ia, width, height)
                            y = xy(landmarks, ib, width, height)
                            if same_seg(a, b, x, y):
                                red = True
                                break
                        updated.append((a, b, "red") + extra if red else pipe)
                    result.pipes = updated

        return result

    if exercise == "bicep_curls":
        return finish(analyze_bicep(landmarks, width, height))

    if exercise == "squat":
        return finish(analyze_squat(landmarks, width, height))

    if exercise == "shoulder_press":
        return finish(analyze_shoulder_press(landmarks, width, height))

    if exercise == "lateral_shoulder_raises":
        return finish(analyze_lateral(landmarks, width, height))

    if exercise == "tricep_extension":
        return finish(analyze_tricep(landmarks, width, height))

    if exercise == "lunges":
        return finish(analyze_lunge(landmarks, width, height))

    if exercise == "push_up":
        return finish(analyze_pushup(landmarks, width, height))

    if exercise == "dumbbell_row":
        return finish(analyze_row(landmarks, width, height))

    if exercise == "sit_up":
        return finish(analyze_situp(landmarks, width, height))

    if exercise == "jumping_jack":
        return finish(analyze_jumping_jack(landmarks, width, height))

    if exercise == "bench_press":
        return finish(analyze_bench_press(landmarks, width, height))

    if exercise == "deadlift":
        return finish(analyze_deadlift(landmarks, width, height))

    if exercise in ("lat_pulldown", "close_grip_lat_pulldown"):
        return ["KEEP TORSO CONTROLLED", "DRIVE ELBOWS DOWN", "CONTROL THE RETURN"]

    if exercise == "front_raise":
        return finish(analyze_front_raise(landmarks, width, height))

    if exercise == "hammer_curl":
        return finish(analyze_hammer_curl(landmarks, width, height))

    if exercise == "calf_raise":
        return finish(analyze_calf_raise(landmarks, width, height))

    if exercise == "glute_bridge":
        return finish(analyze_glute_bridge(landmarks, width, height))

    if exercise == "plank":
        return finish(analyze_plank(landmarks, width, height))

    if exercise == "mountain_climber":
        return finish(analyze_mountain_climber(landmarks, width, height))

    if exercise == "burpee":
        return finish(analyze_burpee(landmarks, width, height))

    if exercise == "step_up":
        return finish(analyze_step_up(landmarks, width, height))

    if exercise == "reverse_lunge":
        return finish(analyze_reverse_lunge(landmarks, width, height))

    if exercise == "chest_fly":
        return finish(analyze_chest_fly(landmarks, width, height))

    if exercise == "incline_dumbbell_press":
        return finish(analyze_incline_dumbbell_press(landmarks, width, height))

    if exercise == "decline_bench_press":
        return finish(analyze_decline_bench_press(landmarks, width, height))

    if exercise == "incline_bench_press":
        return finish(analyze_incline_bench_press(landmarks, width, height))

    if exercise == "dumbbell_bench_press":
        return finish(analyze_dumbbell_bench_press(landmarks, width, height))

    if exercise == "close_grip_bench_press":
        return finish(analyze_close_grip_bench_press(landmarks, width, height))

    if exercise == "push_up_wide_grip":
        return finish(analyze_push_up_wide_grip(landmarks, width, height))

    if exercise == "push_up_diamond":
        return finish(analyze_push_up_diamond(landmarks, width, height))

    if exercise == "incline_push_up":
        return finish(analyze_incline_push_up(landmarks, width, height))

    if exercise == "decline_push_up":
        return finish(analyze_decline_push_up(landmarks, width, height))

    if exercise == "chest_press_machine":
        return finish(analyze_chest_press_machine(landmarks, width, height))

    if exercise == "cable_crossover":
        return finish(analyze_cable_fly_pattern(landmarks, width, height, low=False))

    if exercise == "low_cable_crossover":
        return finish(analyze_cable_fly_pattern(landmarks, width, height, low=True))

    if exercise == "lat_pulldown":
        return finish(analyze_lat_pulldown(landmarks, width, height))

    if exercise == "close_grip_lat_pulldown":
        return finish(analyze_close_grip_lat_pulldown(landmarks, width, height))

    return finish(FormResult(
        "yellow",
        "EXERCISE RULE NOT READY",
        70,
    ))


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
    """Stable, form-gated repetition counter."""

    def __init__(self):
        self.reps = 0
        self.stage = "START"
        self.last_rep_time = 0.0
        self.prev_value = None

    def reset(self):
        self.reps = 0
        self.stage = "START"
        self.last_rep_time = 0.0
        self.prev_value = None

    def _count_cycle(self, value, low, high, direction="low_high_low"):
        if value is None:
            return self.reps

        now = time.time()
        if now - self.last_rep_time < 0.32:
            self.prev_value = value
            return self.reps

        if self.stage == "START":
            if value <= low:
                self.stage = "LOW"
            elif value >= high:
                self.stage = "HIGH"
            self.prev_value = value
            return self.reps

        if direction == "low_high_low":
            if self.stage == "LOW" and value >= high:
                self.stage = "HIGH"
            elif self.stage == "HIGH" and value <= low:
                self.reps += 1
                self.stage = "LOW"
                self.last_rep_time = now
        else:
            if self.stage == "HIGH" and value <= low:
                self.stage = "LOW"
            elif self.stage == "LOW" and value >= high:
                self.reps += 1
                self.stage = "HIGH"
                self.last_rep_time = now

        self.prev_value = value
        return self.reps

    def update(self, exercise, result):
        angles = result.angles or {}

        # Sit-up and jumping-jack expose a movement signal whose opposite
        # phase is intentionally not a green form state. Their counters must
        # see both phases; all existing exercises keep the original
        # form-gated behavior below.
        if exercise == "sit_up":
            return self._count_cycle(
                angles.get("hip"),
                100,
                150,
                "high_low_high",
            )

        if exercise == "jumping_jack":
            return self._count_cycle(
                angles.get("arm_span"),
                1.20,
                1.70,
                "low_high_low",
            )

        # HUMAN-TRAINER REP MODE:
        # GREEN and YELLOW are both valid movement states. A yellow frame
        # means "adjust while moving", not "the repetition did not happen".
        # Only RED blocks rep progression.
        if getattr(result, "status", "red") == "red":
            return self.reps

        if exercise == "bicep_curls":
            return self._count_cycle(angles.get("elbow"), 100, 135, "high_low_high")

        if exercise in ("squat", "lunges"):
            return self._count_cycle(angles.get("knee"), 112, 145, "high_low_high")

        if exercise in ("push_up", "push_up_wide_grip", "push_up_diamond",
                         "incline_push_up", "decline_push_up"):
            return self._count_cycle(angles.get("elbow"), 105, 145, "high_low_high")

        if exercise == "lateral_shoulder_raises":
            return self._count_cycle(angles.get("raise"), 28, 65, "low_high_low")

        if exercise == "shoulder_press":
            return self._count_cycle(angles.get("elbow"), 100, 150, "low_high_low")

        if exercise == "tricep_extension":
            return self._count_cycle(angles.get("elbow"), 80, 145, "low_high_low")

        if exercise == "dumbbell_row":
            return self._count_cycle(angles.get("elbow"), 75, 145, "high_low_high")

        if exercise in (
            "bench_press", "incline_dumbbell_press", "decline_bench_press",
            "incline_bench_press", "dumbbell_bench_press",
            "close_grip_bench_press", "chest_press_machine", "hammer_curl"
        ):
            return self._count_cycle(angles.get("elbow"), 115, 150, "high_low_high")

        if exercise in ("chest_fly", "cable_crossover", "low_cable_crossover"):
            return self._count_cycle(angles.get("fly"), 0.35, 1.25, "low_high_low")

        if exercise in ("lat_pulldown", "close_grip_lat_pulldown"):
            return self._count_cycle(angles.get("elbow"), 95, 145, "high_low_high")

        if exercise == "front_raise":
            return self._count_cycle(angles.get("raise"), 30, 70, "low_high_low")

        if exercise == "deadlift":
            return self._count_cycle(angles.get("knee"), 108, 150, "high_low_high")

        if exercise == "calf_raise":
            return self._count_cycle(angles.get("calf"), 1.00, 1.10, "low_high_low")

        if exercise == "glute_bridge":
            return self._count_cycle(angles.get("hip"), 118, 155, "low_high_low")

        # Plank is a hold, not a repetition-based movement.
        if exercise == "plank":
            return self.reps

        if exercise == "mountain_climber":
            return self._count_cycle(angles.get("knee_drive"), 95, 160, "high_low_high")

        if exercise == "burpee":
            return self._count_cycle(angles.get("knee"), 100, 155, "high_low_high")

        if exercise == "step_up":
            return self._count_cycle(angles.get("knee"), 100, 155, "high_low_high")

        if exercise == "reverse_lunge":
            return self._count_cycle(angles.get("knee"), 105, 150, "high_low_high")

        # Sit-up and jumping-jack are preserved from the original 10-exercise
        # engine behavior rather than inventing a new counting algorithm here.
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

    if exercise in (
        "incline_dumbbell_press",
        "decline_bench_press",
        "incline_bench_press",
        "dumbbell_bench_press",
        "chest_press_machine",
        "cable_crossover",
        "low_cable_crossover",
    ):
        return ["PRESS BOTH ARMS EVENLY", "CONTROL THE RANGE"]

    if exercise == "close_grip_bench_press":
        return ["KEEP ELBOWS CONTROLLED", "PRESS WITH CONTROL"]

    if exercise in (
        "push_up_wide_grip",
        "push_up_diamond",
        "incline_push_up",
        "decline_push_up",
    ):
        return ["KEEP BODY STRAIGHT", "CONTROL CHEST DESCENT"]

    if exercise == "bench_press":
        return ["KEEP WRISTS NEUTRAL", "PRESS BOTH ARMS EVENLY"]

    if exercise == "deadlift":
        return ["KEEP BACK NEUTRAL", "HINGE AT THE HIPS"]

    if exercise in ("lat_pulldown", "close_grip_lat_pulldown"):
        return ["KEEP TORSO CONTROLLED", "DRIVE ELBOWS DOWN", "CONTROL THE RETURN"]

    if exercise == "front_raise":
        return ["KEEP TORSO STILL", "RAISE BOTH ARMS EVENLY"]

    if exercise == "hammer_curl":
        return ["KEEP ELBOWS FIXED", "DON'T SWING"]

    if exercise == "calf_raise":
        return ["KEEP KNEES STABLE", "MOVE WITH CONTROL"]

    if exercise == "glute_bridge":
        return ["EXTEND HIPS", "DON'T OVERARCH"]

    if exercise == "plank":
        return ["KEEP BODY STRAIGHT", "KEEP HIPS ALIGNED"]

    if exercise == "mountain_climber":
        return ["KEEP HIPS CONTROLLED", "CONTROL KNEE DRIVE"]

    if exercise == "burpee":
        return ["KEEP BACK CONTROLLED", "LAND SOFTLY"]

    if exercise == "step_up":
        return ["KEEP KNEE ALIGNED", "CONTROL THE RETURN"]

    if exercise == "reverse_lunge":
        return ["CHEST UP", "KEEP FRONT KNEE ALIGNED"]

    if exercise == "chest_fly":
        return ["KEEP SHOULDERS STABLE", "CONTROL OPEN AND CLOSE"]

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
