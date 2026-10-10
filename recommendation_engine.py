
"""
recommendation_engine.py

FORMFIT AI - Personalized Workout Recommendation Engine

This module is intentionally separate from pose_engine.py.

Flow:
    User Profile
        -> filters
        -> exercise scoring
        -> balanced selection
        -> weekly workout plan

This is a deterministic recommendation engine, not a claim of
medical diagnosis or clinical exercise prescription.
"""

from pathlib import Path
import json
import random

DATA_FILE = Path(__file__).with_name("exercise_database_300_plus.json")


def load_exercises():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["exercises"]


def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def as_set(values):
    if values is None:
        return set()
    if isinstance(values, str):
        values = [values]
    return {normalize(v) for v in values}


def difficulty_rank(level):
    return {
        "beginner": 1,
        "intermediate": 2,
        "advanced": 3,
    }.get(normalize(level), 1)



EQUIPMENT_ALIASES = {
    "dumbbell": "dumbbells",
    "dumbbells": "dumbbells",
    "barbell": "barbell",
    "barbells": "barbell",
    "cable machine": "cable",
    "cable": "cable",
    "resistance bands": "resistance band",
    "resistance band": "resistance band",
    "pullup bar": "pull-up bar",
    "pull-up bar": "pull-up bar",
    "pull up bar": "pull-up bar",
    "dip bars": "dip bar",
    "dip bar": "dip bar",
    "dip station": "dip station",
    "bench": "bench",
    "machine": "machine",
    "kettlebell": "kettlebell",
    "plate": "plate",
    "box": "box",
    "bodyweight": "bodyweight",
    "body weight": "bodyweight",
}


def canonical_equipment(value):
    value = normalize(value)
    return EQUIPMENT_ALIASES.get(value, value)


def canonical_equipment_set(values):
    return {canonical_equipment(v) for v in (values or [])}


def equipment_is_compatible(exercise_equipment, available_equipment):
    """Return True only when the exercise can be performed with selected equipment.

    The database generally lists either alternatives (e.g. dumbbells/barbell)
    or a main implement plus a required support (e.g. barbell + bench).
    Bodyweight is never treated as implicitly available when the user did not
    select it.
    """
    required = canonical_equipment_set(exercise_equipment)
    available = canonical_equipment_set(available_equipment)

    if not required or not available:
        return False

    # Bodyweight-only movements require an explicit Bodyweight selection.
    if required == {"bodyweight"}:
        return "bodyweight" in available

    # If bodyweight is one of several alternatives, another selected primary
    # implement is sufficient; bodyweight itself is only eligible when selected.
    non_bodyweight = required - {"bodyweight"}
    if "bodyweight" in required and "bodyweight" not in available:
        required = non_bodyweight

    if not required:
        return "bodyweight" in available

    # Bench/bar/box/pull-up supports listed alongside an implement are
    # treated as required supports, not alternatives.
    support_items = {"bench", "box", "pull-up bar", "dip bar", "dip station"}
    supports = required & support_items
    implements = required - support_items

    if supports:
        if not supports.issubset(available):
            return False
        if not implements:
            return True
        return bool(implements & available)

    # Otherwise the listed equipment represents alternative ways to perform
    # the movement, so at least one selected implement is enough.
    return bool(required & available)


def split_targets_for_day(split_name):
    name = normalize(split_name)
    mapping = {
        "push": {"chest", "shoulders", "triceps", "deltoids", "triceps"},
        "pull": {"back", "biceps", "rear deltoids"},
        "legs": {"quadriceps", "hamstrings", "glutes", "calves"},
        "upper body": {"chest", "back", "shoulders", "biceps", "triceps", "rear deltoids", "deltoids"},
        "lower body": {"quadriceps", "hamstrings", "glutes", "calves"},
        "chest": {"chest"},
        "back": {"back"},
        "shoulders": {"shoulders", "deltoids", "lateral deltoids", "anterior deltoids"},
        "arms": {"biceps", "triceps", "forearms", "brachialis"},
    }
    return mapping.get(name)


def exercise_fits_split(exercise, split_name):
    """Hard split gate: an explicit split may not leak into another body part."""
    name = normalize(split_name)
    if name in {"", "auto", "full body", "full body a", "full body b", "conditioning"}:
        return True

    targets = split_targets_for_day(name)
    if not targets:
        return True

    primary = {normalize(x) for x in exercise.get("primary_muscles", [])}
    secondary = {normalize(x) for x in exercise.get("secondary_muscles", [])}

    # Primary-muscle match is preferred. Secondary-only overlap is allowed only
    # for compound movements so a Push day does not fill with Pull/Leg work.
    if primary & targets:
        return True

    if name == "upper body":
        return bool((primary | secondary) & targets)

    return False

def score_exercise(exercise_id, exercise, profile):
    """
    Score one exercise from 0-100.

    Factors:
      - goal / target muscle
      - experience compatibility
      - equipment
      - preferred workout style
      - available time
      - form-check availability
    """
    score = 50.0

    experience = normalize(profile.get("experience", "beginner"))
    goal = normalize(profile.get("goal", "general fitness"))

    available_equipment = as_set(
        profile.get("equipment", ["bodyweight"])
    )

    target_muscles = as_set(
        profile.get("target_muscles", [])
    )

    favorite_exercises = as_set(profile.get("favorite_exercises", []))
    disliked_exercises = as_set(profile.get("disliked_exercises", []))
    avoid_exercises = as_set(profile.get("avoid_exercises", []))

    exercise_primary = as_set(
        exercise.get("primary_muscles", [])
    )

    exercise_secondary = as_set(
        exercise.get("secondary_muscles", [])
    )

    exercise_equipment = as_set(
        exercise.get("equipment", [])
    )

    # --------------------------------------------------------
    # Learned user preference matching
    # --------------------------------------------------------
    normalized_id = normalize(exercise_id)
    if normalized_id in favorite_exercises:
        score += 18
    if normalized_id in disliked_exercises:
        score -= 22
    if normalized_id in avoid_exercises:
        score -= 70

    # --------------------------------------------------------
    # Experience matching
    # --------------------------------------------------------
    exp_rank = difficulty_rank(experience)
    ex_rank = difficulty_rank(exercise.get("difficulty"))

    if ex_rank == exp_rank:
        score += 15
    elif ex_rank < exp_rank:
        score += 8
    elif ex_rank == exp_rank + 1:
        score -= 12
    else:
        score -= 25

    # --------------------------------------------------------
    # Equipment compatibility — STRICT user selection
    # --------------------------------------------------------
    equipment_match = equipment_is_compatible(
        exercise_equipment,
        available_equipment,
    )

    if equipment_match:
        score += 16
    else:
        score -= 60

    # --------------------------------------------------------
    # Target muscle match
    # --------------------------------------------------------
    if target_muscles:
        direct = exercise_primary & target_muscles
        secondary = exercise_secondary & target_muscles

        score += min(20, len(direct) * 10)
        score += min(8, len(secondary) * 4)

    # --------------------------------------------------------
    # Goal heuristics
    # --------------------------------------------------------
    if goal in {"muscle gain", "hypertrophy", "build muscle"}:
        if ex_rank <= 2:
            score += 5

    elif goal in {"strength", "build strength"}:
        if normalize(exercise.get("difficulty")) in {
            "intermediate",
            "advanced",
        }:
            score += 6

    elif goal in {"fat loss", "weight loss", "conditioning"}:
        if exercise.get("category") in {
            "Cardio",
            "Full Body",
        }:
            score += 12

    elif goal in {"mobility", "flexibility"}:
        if exercise.get("category") == "Mobility":
            score += 20

    elif goal in {"general fitness", "fitness"}:
        if exercise.get("category") in {
            "Full Body",
            "Legs",
            "Back",
            "Chest",
        }:
            score += 4

    # --------------------------------------------------------
    # Prefer tested form-check exercises when possible.
    # --------------------------------------------------------
    if exercise.get("form_check_status") == "READY":
        score += 5
    elif exercise.get("form_check_status") == "BASIC":
        score += 2

    return max(0, min(100, round(score)))


def filter_exercises(profile):
    exercises = load_exercises()

    result = []

    for exercise_id, exercise in exercises.items():
        score = score_exercise(
            exercise_id,
            exercise,
            profile,
        )

        # Hard user preference filter: exercises explicitly marked
        # as "avoid" never enter a generated plan.
        avoid_exercises = as_set(profile.get("avoid_exercises", []))
        if normalize(exercise_id) in avoid_exercises:
            continue

        # Hard equipment filter — never assume Bodyweight.
        equipment = as_set(profile.get("equipment", []))
        exercise_equipment = as_set(exercise.get("equipment", []))
        if not equipment_is_compatible(exercise_equipment, equipment):
            continue

        # Hard split filter for explicit user-selected splits.
        split_name = profile.get("split_day") or profile.get("split") or "auto"
        if not exercise_fits_split(exercise, split_name):
            continue

        # Avoid advanced exercises for beginners unless explicitly
        # requested.
        experience = normalize(
            profile.get("experience", "beginner")
        )

        if (
            experience == "beginner"
            and normalize(exercise.get("difficulty")) == "advanced"
        ):
            continue

        result.append({
            "id": exercise_id,
            "score": score,
            "exercise": exercise,
        })

    result.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return result


def choose_exercises(profile, count=6):
    """
    Pick a balanced set instead of simply returning the top six
    exercises from the same muscle/category.
    """
    candidates = filter_exercises(profile)

    selected = []
    used_categories = set()
    used_muscles = set()
    previously_used = {normalize(x) for x in profile.get("weekly_used_exercises", [])}

    for item in candidates:
        ex = item["exercise"]
        category = ex.get("category")
        primary = set(ex.get("primary_muscles", []))

        # Do not repeat the same movement across a week unless the candidate
        # pool is exhausted.
        if normalize(item["id"]) in previously_used and len(selected) < count:
            continue

        # First pass: encourage variety.
        if (
            category in used_categories
            and len(selected) < max(3, count - 2)
        ):
            continue

        if primary & used_muscles and len(selected) < count - 1:
            continue

        selected.append(item)
        used_categories.add(category)
        used_muscles.update(primary)

        if len(selected) >= count:
            break

    # Fallback if variety or weekly-repeat filters were too strict.
    if len(selected) < count:
        selected_ids = {x["id"] for x in selected}

        for item in candidates:
            if item["id"] not in selected_ids:
                selected.append(item)
            if len(selected) >= count:
                break

    return selected[:count]


def prescription(exercise, profile):
    experience = normalize(
        profile.get("experience", "beginner")
    )
    goal = normalize(
        profile.get("goal", "general fitness")
    )

    if goal in {"strength", "build strength"}:
        if experience == "beginner":
            return 3, "6-8", 120
        return 4, "5-8", 150

    if goal in {"muscle gain", "hypertrophy", "build muscle"}:
        if experience == "beginner":
            return 3, "8-12", 90
        return 3, "8-12", 90

    if goal in {"fat loss", "weight loss", "conditioning"}:
        return 3, "10-15", 60

    if goal in {"mobility", "flexibility"}:
        return 2, "30-45 sec", 45

    return 3, "8-12", 75



# ------------------------------------------------------------
# Intelligent workout ordering
# ------------------------------------------------------------
# Selection decides WHICH exercises belong in a session.
# Ordering decides WHEN they should be performed.
# The order follows the chosen split's muscle-group sequence and
# places higher-demand compound movements before isolation work.
#
# This does not change filtering, scoring, equipment rules, reps,
# sets, rest, or form-check behavior.
# ------------------------------------------------------------

_SPLIT_GROUP_ORDER = {
    "push": ["chest", "shoulders", "triceps"],
    "pull": ["back", "rear deltoids", "biceps", "forearms"],
    "legs": ["quadriceps", "glutes", "hamstrings", "calves"],
    "upper body": ["chest", "back", "shoulders", "biceps", "triceps"],
    "lower body": ["quadriceps", "hamstrings", "glutes", "calves"],
    "chest": ["chest"],
    "back": ["back"],
    "shoulders": ["shoulders", "rear deltoids"],
    "arms": ["biceps", "triceps", "forearms"],
    "full body": [
        "quadriceps", "glutes", "hamstrings", "chest",
        "back", "shoulders", "biceps", "triceps", "calves"
    ],
    "full body a": [
        "quadriceps", "glutes", "chest", "back",
        "shoulders", "biceps", "triceps", "calves"
    ],
    "full body b": [
        "chest", "back", "quadriceps", "hamstrings",
        "shoulders", "biceps", "triceps", "calves"
    ],
}

_MUSCLE_ALIASES = {
    "chest": "chest",
    "pectorals": "chest",
    "pecs": "chest",
    "back": "back",
    "latissimus dorsi": "back",
    "lats": "back",
    "rhomboids": "back",
    "trapezius": "back",
    "erector spinae": "back",
    "shoulders": "shoulders",
    "deltoids": "shoulders",
    "lateral deltoids": "shoulders",
    "anterior deltoids": "shoulders",
    "front deltoids": "shoulders",
    "rear deltoids": "rear deltoids",
    "posterior deltoids": "rear deltoids",
    "biceps": "biceps",
    "brachialis": "biceps",
    "triceps": "triceps",
    "forearms": "forearms",
    "quadriceps": "quadriceps",
    "quads": "quadriceps",
    "hamstrings": "hamstrings",
    "glutes": "glutes",
    "gluteus maximus": "glutes",
    "calves": "calves",
    "gastrocnemius": "calves",
    "soleus": "calves",
}

# Common multi-joint movements should lead their muscle group.
# The keyword list is deliberately conservative; unknown movements
# fall behind known compounds but remain in their correct muscle group.
_COMPOUND_KEYWORDS = (
    "press", "bench", "push-up", "push up", "row", "pull-up", "pull up",
    "chin-up", "chin up", "squat", "deadlift", "lunge", "split squat",
    "step-up", "step up", "dip", "clean", "snatch", "thruster",
    "overhead", "pulldown", "pull down", "hip thrust", "leg press"
)


def _canonical_muscle(value):
    value = normalize(value)
    return _MUSCLE_ALIASES.get(value, value)


def _muscle_groups_for_exercise(exercise):
    groups = []
    for muscle in exercise.get("primary_muscles", []) + exercise.get("secondary_muscles", []):
        group = _canonical_muscle(muscle)
        if group not in groups:
            groups.append(group)
    return groups


def _primary_group_for_split(exercise, split_name):
    # Group by PRIMARY muscle first. Secondary muscles must never pull an
    # exercise into an earlier block (e.g. triceps-only work should not appear
    # inside the chest block just because chest is a secondary muscle).
    primary_groups = []
    for muscle in exercise.get("primary_muscles", []):
        group = _canonical_muscle(muscle)
        if group not in primary_groups:
            primary_groups.append(group)

    group_order = _SPLIT_GROUP_ORDER.get(normalize(split_name), [])
    for preferred in group_order:
        if preferred in primary_groups:
            return preferred

    return primary_groups[0] if primary_groups else "other"


_MOVEMENT_PRIORITY = (
    # Highest-demand / main compounds first.
    (0, ("squat", "front squat", "goblet squat", "back squat")),
    (1, ("deadlift", "romanian deadlift", "rdl", "hip thrust")),
    (2, ("bench press", "incline bench", "decline bench", "dumbbell bench")),
    (3, ("pull-up", "pull up", "chin-up", "chin up", "pulldown", "pull down", "row")),
    (4, ("shoulder press", "overhead press", "military press")),
    (5, ("lunge", "split squat", "step-up", "step up")),
    (6, ("dip", "push-up", "push up")),
    (7, ("fly", "crossover", "raise", "extension", "curl", "kickback", "calf")),
)


def _movement_priority(name):
    name = normalize(name)
    for rank, keywords in _MOVEMENT_PRIORITY:
        if any(keyword in name for keyword in keywords):
            return rank
    return 8


def _exercise_order_key(exercise, split_name):
    group_order = _SPLIT_GROUP_ORDER.get(
        normalize(split_name),
        []
    )
    group = _primary_group_for_split(exercise, split_name)

    try:
        group_rank = group_order.index(group)
    except ValueError:
        group_rank = len(group_order) + 1

    name = normalize(exercise.get("name", ""))
    category = normalize(exercise.get("category", ""))

    movement_rank = _movement_priority(name)
    primary_count = len(exercise.get("primary_muscles", []) or [])
    primary_rank = -primary_count

    form_rank = {
        "ready": 0,
        "basic": 1,
        "coming_soon": 2,
    }.get(normalize(exercise.get("form_check_status")), 2)

    return (
        group_rank,
        movement_rank,
        primary_rank,
        form_rank,
        category,
        name,
    )


def order_selected_exercises(selected, split_name):
    """Arrange already-selected exercises into a coach-like session order.

    Examples:
      Push  -> chest block -> shoulder block -> triceps block
      Pull  -> back block -> rear-delt block -> biceps -> forearms
      Legs  -> quads -> glutes -> hamstrings -> calves

    No exercise is added or removed here.
    """
    return sorted(
        selected,
        key=lambda item: _exercise_order_key(item["exercise"], split_name),
    )

def build_day(profile, day_number, day_name):
    count = int(profile.get("exercises_per_day", 6))
    day_profile = dict(profile)
    day_profile["split_day"] = day_name

    chosen = choose_exercises(
        day_profile,
        count=count,
    )

    # Keep the selected exercises intact; only arrange their session order.
    chosen = order_selected_exercises(chosen, day_name)

    workout = []

    for index, item in enumerate(chosen, start=1):
        ex = item["exercise"]

        sets, reps, rest = prescription(
            ex,
            profile,
        )

        workout.append({
            "order": index,
            "exercise_id": item["id"],
            "exercise": ex["name"],
            "category": ex.get("category"),
            "primary_muscles": ex.get(
                "primary_muscles",
                [],
            ),
            "sets": sets,
            "reps": reps,
            "rest_seconds": rest,
            "difficulty": ex.get("difficulty"),
            "equipment": ex.get("equipment", []),
            "camera_view": ex.get(
                "recommended_views",
                [],
            ),
            "form_check_status": ex.get(
                "form_check_status",
                "COMING_SOON",
            ),
            "coaching": ex.get(
                "coaching",
                [],
            ),
            "score": item["score"],
        })

    return {
        "day": day_number,
        "name": day_name,
        "warmup_minutes": 5,
        "exercises": workout,
    }


def resolve_split_names(split_choice, days):
    """
    Return exactly `days` training-day names for the user's selected split.

    `auto` preserves the previous adaptive behavior. Explicit splits are
    cycled/truncated to fit 1–7 training days so the UI choice never creates
    an invalid plan length.
    """
    split = normalize(split_choice or "auto")

    if split in {"", "auto", "ai", "let formfit decide"}:
        if days == 1:
            return ["Full Body"]
        if days == 2:
            return ["Full Body A", "Full Body B"]
        if days == 3:
            return ["Full Body", "Full Body", "Full Body"]
        if days == 4:
            return ["Upper Body", "Lower Body", "Upper Body", "Lower Body"]
        if days == 5:
            return ["Upper Body", "Lower Body", "Push", "Pull", "Legs"]
        return [
            "Push", "Pull", "Legs",
            "Upper Body", "Lower Body",
            "Full Body", "Conditioning",
        ]

    patterns = {
        "push_pull_legs": ["Push", "Pull", "Legs"],
        "full_body": ["Full Body"],
        "upper_lower": ["Upper Body", "Lower Body"],
        "one_body_part": [
            "Chest", "Back", "Shoulders", "Arms", "Legs",
        ],
        "bro_split": [
            "Chest", "Back", "Shoulders", "Arms", "Legs",
        ],
    }

    pattern = patterns.get(split)
    if not pattern:
        return resolve_split_names("auto", days)

    return [pattern[i % len(pattern)] for i in range(days)]


def split_target_muscles(split_name):
    split = normalize(split_name)

    if split == "push":
        return [
            "Chest",
            "Shoulders",
            "Triceps",
        ]

    if split == "pull":
        return [
            "Back",
            "Biceps",
            "Rear Deltoids",
        ]

    if split == "legs":
        return [
            "Quadriceps",
            "Hamstrings",
            "Glutes",
            "Calves",
        ]

    if split == "upper body":
        return [
            "Chest",
            "Back",
            "Shoulders",
            "Biceps",
            "Triceps",
        ]

    if split == "lower body":
        return [
            "Quadriceps",
            "Hamstrings",
            "Glutes",
            "Calves",
        ]

    if split == "chest":
        return [
            "Chest",
        ]

    if split == "back":
        return [
            "Back",
        ]

    if split == "shoulders":
        return [
            "Shoulders",
        ]

    if split == "arms":
        return [
            "Biceps",
            "Triceps",
            "Forearms",
        ]

    if split == "full body" or split in {"full body a", "full body b"}:
        return [
            "Chest",
            "Back",
            "Shoulders",
            "Biceps",
            "Triceps",
            "Quadriceps",
            "Hamstrings",
            "Glutes",
            "Calves",
        ]

    return None


def build_weekly_plan(profile):
    days = int(profile.get("days_per_week", 3))
    days = max(1, min(7, days))

    split_choice = normalize(profile.get("split", "auto"))
    names = resolve_split_names(split_choice, days)

    plan = []

    for i in range(days):
        day_profile = dict(profile)
        split_name = names[i]

        # Split-specific target hints.
        target_muscles = split_target_muscles(split_name)
        if target_muscles:
            day_profile["target_muscles"] = target_muscles

        if normalize(split_name) == "conditioning":
            day_profile["goal"] = "conditioning"

        day_profile["weekly_used_exercises"] = [
            ex["exercise_id"]
            for day in plan
            for ex in day.get("exercises", [])
        ]

        day_result = build_day(
            day_profile,
            i + 1,
            split_name,
        )
        plan.append(day_result)

    return {
        "plan_name": "FORMFIT AI Personalized Plan",
        "profile": {
            **profile,
            "split": split_choice or "auto",
        },
        "split": split_choice or "auto",
        "days_per_week": days,
        "days": plan,
        "note": (
            "This is an exercise-selection and workout-planning "
            "engine. It is not medical advice."
        ),
    }


if __name__ == "__main__":
    demo_profile = {
        "goal": "muscle gain",
        "experience": "beginner",
        "days_per_week": 3,
        "exercises_per_day": 6,
        "equipment": [
            "Dumbbells",
        ],
        "target_muscles": [
            "Chest",
            "Back",
            "Shoulders",
            "Biceps",
            "Triceps",
        ],
    }

    plan = build_weekly_plan(demo_profile)

    print("=" * 60)
    print("FORMFIT AI - RECOMMENDATION ENGINE")
    print("=" * 60)

    for day in plan["days"]:
        print()
        print(day["day"], "-", day["name"])

        for ex in day["exercises"]:
            print(
                f'{ex["order"]}. {ex["exercise"]} '
                f'| {ex["sets"]} x {ex["reps"]} '
                f'| {ex["rest_seconds"]} sec'
            )
