
let exercises = [];
let currentExercise = null;
let cameraStream = null;
let resumeCameraAfterSave = false;

let poseTimer = null;
let frameCanvas = null;
let poseBusy = false;
let requestSerial = 0;

// V9: browser-side MediaPipe keeps live pose tracking independent from
// the Python form-analysis API. The API receives landmarks only.
let browserPose = null;
let browserPoseReady = false;
let browserPoseBusy = false;

// Adaptive camera-rate mode:
// There is intentionally NO fixed 30/60 FPS timer here. Browser MediaPipe
// receives frames from the actual <video> stream, so the analysis follows
// the camera's delivered frame rate.


// ------------------------------------------------------------
// SMOOTH PIPE STATE
// ------------------------------------------------------------
// The Python engine remains responsible for form decisions.
// These values only smooth what the user sees on screen.
const visual = {
  pipes: [],
  targets: [],
  score: 0,
  reps: 0,
  status: "yellow",
  message: "",
  lastView: "",
  lastTime: performance.now(),
  frameId: 0,

  // Live geometry is driven by the newest browser MediaPipe result.
  // API responses provide coaching/status only and never block rendering.
  liveLandmarks: [],
  smoothedLandmarks: [],
  landmarkLowConfidenceFrames: [],
  liveLandmarkPrev: [],
  liveLandmarkTime: 0,
  liveSegments: [],
  pipeStatusByKey: new Map()
};

const LIVE_SEGMENTS = [
  [0, 11], [0, 12], [11, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27],
  [24, 26], [26, 28]
];


// Stable single-person target lock: reject abrupt jumps to a background person.
// This deliberately works on torso landmarks so seated/partial-body exercises remain supported.
let poseTargetLockState = null;

function poseTargetMetrics(landmarks) {
  if (!Array.isArray(landmarks) || landmarks.length < 25) return null;
  const visible = (i) => {
    const p = landmarks[i];
    return p && Number.isFinite(p.x) && Number.isFinite(p.y) &&
      Number(p.visibility ?? 1) >= 0.35 && Number(p.presence ?? 1) >= 0.35;
  };
  const shoulderIndices = [11, 12].filter(visible);
  if (shoulderIndices.length !== 2) return null;
  const torsoIndices = [11, 12, 23, 24].filter(visible);
  const points = torsoIndices.length >= 3 ? torsoIndices : shoulderIndices;
  const center = points.reduce((a, i) => ({ x: a.x + landmarks[i].x / points.length, y: a.y + landmarks[i].y / points.length }), {x:0,y:0});
  const left = landmarks[11], right = landmarks[12];
  const shoulderWidth = Math.hypot(left.x - right.x, left.y - right.y);
  if (!Number.isFinite(shoulderWidth) || shoulderWidth < 0.025) return null;
  return { x: center.x, y: center.y, scale: shoulderWidth };
}

function acceptPoseTarget(landmarks) {
  const candidate = poseTargetMetrics(landmarks);
  if (!candidate) return { accepted: false, reason: 'low-confidence' };
  if (!poseTargetLockState) {
    poseTargetLockState = {...candidate};
    return { accepted: true, reason: 'locked' };
  }
  const displacement = Math.hypot(candidate.x - poseTargetLockState.x, candidate.y - poseTargetLockState.y);
  const scaleRatio = candidate.scale / Math.max(poseTargetLockState.scale, 0.001);
  // Sudden center jumps, especially with an extreme scale change, usually mean MediaPipe switched people.
  // A scale change alone is not enough: turning sideways can narrow shoulder width.
  // Reject rather than feed another person's skeleton into rep/form analysis.
  if (displacement > 0.19 || (displacement > 0.10 && (scaleRatio > 2.2 || scaleRatio < 0.35))) {
    return { accepted: false, reason: 'target-switch' };
  }
  // Follow gradual user movement without allowing one frame to move the lock.
  const alpha = 0.12;
  poseTargetLockState.x += (candidate.x - poseTargetLockState.x) * alpha;
  poseTargetLockState.y += (candidate.y - poseTargetLockState.y) * alpha;
  poseTargetLockState.scale += (candidate.scale - poseTargetLockState.scale) * alpha;
  return { accepted: true, reason: 'tracking' };
}

function resetPoseTargetLock() {
  poseTargetLockState = null;
}

let formClockTimer = null;
let formStartTime = 0;

// REP DISPLAY:
// Backend RepCounter is authoritative. GREEN and YELLOW completed cycles
// are valid repetitions; RED is the hard rejection state.
let acceptedReps = 0;
let lastRawReps = 0;

const state = {
  goal: "muscle gain",
  equipment: [],
  split: "auto"
};

const workoutMemory = {
  favorite_exercises: [],
  disliked_exercises: [],
  avoid_exercises: [],
  notes: []
};

let activeWorkoutProfile = null;
let activeWorkoutPlan = null;
let savedWorkoutCache = [];
let activeSavedWorkoutId = null;

// PRE-MAPPED REFERENCE DEMOS — UI ONLY.
// Automatic YouTube fallback is also UI-only: form/model/camera logic is untouched.
const PREMAPPED_DEMOS = {
  "squat": { id: "OOsb9DNs8dI", source: "Squat reference" },
  "bicep_curls": { id: "pQfJR-sSIvA", source: "Bicep Curl reference" },
  "shoulder_press": { id: "fRPzHslb9XU", source: "University of Arkansas • Shoulder Press" },
  "lateral_shoulder_raises": { id: "c7zMmbWkUPw", source: "Lateral Raise reference" },
  "tricep_extension": { id: "_gsUck-7M74", source: "Tricep Extension reference" },
  "lunges": { id: "QF0BQS2W80k", source: "Lunge reference" },
  "push_up": { id: "WDIpL0pjun0", source: "Push-Up reference" },
  "dumbbell_row": { id: "roCP6wCXPqo", source: "Dumbbell Row reference" },
  "sit_up": { id: "1fbU_MkV7NE", source: "Sit-Up reference" },
  "jumping_jack": { id: "uLVt6u15L98", source: "Jumping Jack reference" },
  "bench_press": { id: "Zw6qCAFsV0w", source: "BarBend • Bench Press" },
  "deadlift": { id: "Z6gcRfPNcZo", source: "NASM • Deadlift" },
  "front_raise": { id: "c7zMmbWkUPw", source: "Shoulder raise reference" },
  "hammer_curl": { id: "TwD-YGVP4Bk", source: "Howcast • Hammer Curl" },
  "calf_raise": { id: "1lKjFPrYqf0", source: "BarBend • Calf Raise" },
  "glute_bridge": { id: "sh63qy5EV_8", source: "BarBend • Glute Bridge" },
  "plank": { id: "mwlp75MS6Rg", source: "NASM • Plank" },
  "mountain_climber": { id: "kLh-uczlPLg", source: "PureGym • Mountain Climber" },
  "burpee": { id: "mUYJqe_sJFE", source: "Minus The Gym • Burpee" },
  "step_up": { id: "URHdW9js6DM", source: "NASM • Step Up" },
  "reverse_lunge": { id: "lKhZvT_NkOs", source: "NASM • Reverse Lunge" },
  "chest_fly": { id: "mLgYNdxj-Vw", source: "Jeremy Ethier • Chest Fly" },
  "incline_dumbbell_press": { id: "WLTU1j7Ur8M", source: "BarBend • Dumbbell Bench Press" },
  "decline_bench_press": { id: "Zw6qCAFsV0w", source: "BarBend • Bench Press" },
  "incline_bench_press": { id: "Zw6qCAFsV0w", source: "BarBend • Bench Press" },
  "dumbbell_bench_press": { id: "WLTU1j7Ur8M", source: "BarBend • Dumbbell Bench Press" },
  "close_grip_bench_press": { id: "Zfi0cIJi6c", source: "BarBend • Close-Grip Incline Press" },
  "push_up_wide_grip": { id: "WDIpL0pjun0", source: "Push-Up reference" },
  "push_up_diamond": { id: "WDIpL0pjun0", source: "Push-Up reference" },
  "incline_push_up": { id: "WDIpL0pjun0", source: "Push-Up reference" },
  "decline_push_up": { id: "WDIpL0pjun0", source: "Push-Up reference" },
  "chest_press_machine": { id: "2y6ntGVg4dw", source: "BarBend • Chest Press Machine" },
  "cable_crossover": { id: "8Um35Es-ROE", source: "BarBend • Cable Fly" },
  "low_cable_crossover": { id: "8Um35Es-ROE", source: "BarBend • Cable Fly" },
  "lat_pulldown": { id: "SALxEARiMkw", source: "ATHLEAN-X • Lat Pulldown" },
  "close_grip_lat_pulldown": { id: "SALxEARiMkw", source: "ATHLEAN-X • Lat Pulldown" },
};

// Candidate pools are only for the reference-video card.
// When a creator disables embedding, retires a video, or YouTube reports
// an iframe/player error, the next candidate is tried automatically.
const VIDEO_FALLBACK_POOLS = {
  back: [
    { id: "SALxEARiMkw", source: "ATHLEAN-X • Lat Pulldown" },
  ],
  arms: [
    { id: "4hTUCDUQaNA", source: "Lateral Raise • alternate reference" },
    { id: "pQfJR-sSIvA", source: "Bicep Curl reference" },
    { id: "TwD-YGVP4Bk", source: "Hammer Curl reference" },
    { id: "_gsUck-7M74", source: "Tricep Extension reference" },
    { id: "fRPzHslb9XU", source: "Shoulder Press reference" },
    { id: "c7zMmbWkUPw", source: "Shoulder Raise reference" },
  ],
  legs: [
    { id: "OOsb9DNs8dI", source: "Squat reference" },
    { id: "QF0BQS2W80k", source: "Lunge reference" },
    { id: "lKhZvT_NkOs", source: "Reverse Lunge reference" },
    { id: "URHdW9js6DM", source: "Step Up reference" },
    { id: "1lKjFPrYqf0", source: "Calf Raise reference" },
    { id: "Z6gcRfPNcZo", source: "Deadlift reference" },
    { id: "sh63qy5EV_8", source: "Glute Bridge reference" },
  ],
  chest: [
    { id: "Zw6qCAFsV0w", source: "Bench Press reference" },
    { id: "WLTU1j7Ur8M", source: "Dumbbell Bench Press reference" },
    { id: "Zfi0cIJi6c", source: "Close-Grip Press reference" },
    { id: "2y6ntGVg4dw", source: "Chest Press Machine reference" },
    { id: "mLgYNdxj-Vw", source: "Chest Fly reference" },
    { id: "8Um35Es-ROE", source: "Cable Fly reference" },
    { id: "WDIpL0pjun0", source: "Push-Up reference" },
  ],
  core: [
    { id: "1fbU_MkV7NE", source: "Sit-Up reference" },
    { id: "mwlp75MS6Rg", source: "Plank reference" },
    { id: "kLh-uczlPLg", source: "Mountain Climber reference" },
    { id: "mUYJqe_sJFE", source: "Burpee reference" },
    { id: "uLVt6u15L98", source: "Jumping Jack reference" },
  ],
};

const VIDEO_FALLBACK_POOLS_BACK = [{ id: "SALxEARiMkw", source: "ATHLEAN-X • Lat Pulldown" }];

const VIDEO_POOL_BY_EXERCISE = {
  lateral_shoulder_raises: "arms",
  front_raise: "arms",
  bicep_curls: "arms",
  hammer_curl: "arms",
  shoulder_press: "arms",
  tricep_extension: "arms",

  squat: "legs",
  lunges: "legs",
  reverse_lunge: "legs",
  step_up: "legs",
  calf_raise: "legs",
  deadlift: "legs",
  glute_bridge: "legs",

  bench_press: "chest",
  incline_dumbbell_press: "chest",
  decline_bench_press: "chest",
  incline_bench_press: "chest",
  dumbbell_bench_press: "chest",
  close_grip_bench_press: "chest",
  push_up: "chest",
  push_up_wide_grip: "chest",
  push_up_diamond: "chest",
  incline_push_up: "chest",
  decline_push_up: "chest",
  chest_press_machine: "chest",
  chest_fly: "chest",
  cable_crossover: "chest",
  low_cable_crossover: "chest",
  lat_pulldown: "back",
  close_grip_lat_pulldown: "back",

  sit_up: "core",
  plank: "core",
  mountain_climber: "core",
  burpee: "core",
  jumping_jack: "core",
  dumbbell_row: "arms",
};

let referencePlayer = null;
let referencePlayerExerciseId = "";
let referenceCandidates = [];
let referenceCandidateIndex = -1;
let youtubeApiPromise = null;
let referenceProbeTimer = null;
let referenceLoadSerial = 0;
let referenceProbeHost = null;

function dedupeVideoCandidates(items) {
  const seen = new Set();
  return (items || []).filter(item => {
    if (!item?.id || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function getReferenceCandidates(exercise) {
  const primary = PREMAPPED_DEMOS[exercise?.id];
  const poolName = VIDEO_POOL_BY_EXERCISE[exercise?.id];
  const pool = VIDEO_FALLBACK_POOLS[poolName] || [];
  return dedupeVideoCandidates([primary, ...pool]);
}

function loadYouTubeIframeAPI() {
  if (window.YT && typeof window.YT.Player === "function") {
    return Promise.resolve(window.YT);
  }
  if (youtubeApiPromise) return youtubeApiPromise;

  youtubeApiPromise = new Promise(resolve => {
    const finish = () => resolve(
      window.YT && typeof window.YT.Player === "function" ? window.YT : null
    );
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      try { if (typeof previous === "function") previous(); } catch (_) {}
      finish();
    };
    const existing = document.querySelector('script[data-formfit-youtube="1"]');
    if (!existing) {
      const script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      script.async = true;
      script.dataset.formfitYoutube = "1";
      script.onerror = finish;
      document.head.appendChild(script);
    }
    setTimeout(finish, 8000);
  });
  return youtubeApiPromise;
}

function setReferenceFrameFallbackMessage(text) {
  const source = $("#premappedDemoSource");
  if (source) source.textContent = text;
}

function destroyReferenceProbe() {
  if (referenceProbeTimer) {
    clearTimeout(referenceProbeTimer);
    referenceProbeTimer = null;
  }
  if (referencePlayer && typeof referencePlayer.destroy === "function") {
    try { referencePlayer.destroy(); } catch (_) {}
  }
  referencePlayer = null;
}

function ensureReferenceProbeHost() {
  if (referenceProbeHost) return referenceProbeHost;
  referenceProbeHost = document.createElement("div");
  referenceProbeHost.id = "formfit-reference-probe";
  referenceProbeHost.setAttribute("aria-hidden", "true");
  referenceProbeHost.style.position = "fixed";
  referenceProbeHost.style.width = "1px";
  referenceProbeHost.style.height = "1px";
  referenceProbeHost.style.left = "-10000px";
  referenceProbeHost.style.top = "-10000px";
  referenceProbeHost.style.opacity = "0";
  referenceProbeHost.style.pointerEvents = "none";
  referenceProbeHost.style.overflow = "hidden";
  document.body.appendChild(referenceProbeHost);
  return referenceProbeHost;
}

function loadReferenceCandidate(index) {
  const iframe = $("#premappedDemoFrameVideo");
  const title = $("#premappedDemoTitle");
  if (!iframe || !title || !currentExercise) return;

  destroyReferenceProbe();

  if (index >= referenceCandidates.length) {
    setReferenceFrameFallbackMessage("No playable reference found — Watch on YouTube");
    return;
  }

  referenceCandidateIndex = index;
  const candidate = referenceCandidates[index];
  const loadSerial = ++referenceLoadSerial;
  const exerciseIdAtStart = currentExercise.id;

  title.textContent = `${currentExercise.name} Demo`;
  setReferenceFrameFallbackMessage(candidate.source);

  // IMPORTANT: the visible demo stays a plain YouTube iframe.
  // The API is used only by a hidden probe so it can never blank the UI video.
  iframe.src =
    `https://www.youtube-nocookie.com/embed/${candidate.id}` +
    `?autoplay=1&mute=1&controls=1&rel=0&playsinline=1`;

  // Probe this candidate in the background. If YouTube reports an error,
  // automatically try the next candidate without disturbing the visible iframe.
  loadYouTubeIframeAPI().then(YT => {
    if (!YT || !currentExercise) return;
    if (loadSerial !== referenceLoadSerial || currentExercise.id !== exerciseIdAtStart) return;

    const host = ensureReferenceProbeHost();
    host.innerHTML = `<div id="formfit-reference-probe-player"></div>`;

    referencePlayer = new YT.Player("formfit-reference-probe-player", {
      width: 1,
      height: 1,
      videoId: candidate.id,
      playerVars: {
        autoplay: 0,
        controls: 0,
        rel: 0,
        playsinline: 1
      },
      events: {
        onReady: event => {
          try { event.target.mute(); } catch (_) {}
          referenceProbeTimer = setTimeout(() => {
            if (loadSerial !== referenceLoadSerial) return;
            try { event.target.stopVideo(); } catch (_) {}
          }, 2500);
        },
        onError: event => {
          if (loadSerial !== referenceLoadSerial) return;
          if (referenceCandidateIndex < referenceCandidates.length - 1) {
            loadReferenceCandidate(referenceCandidateIndex + 1);
          } else {
            setReferenceFrameFallbackMessage("No playable reference found — Watch on YouTube");
          }
        }
      }
    });
  }).catch(() => {
    // Visible direct iframe remains untouched if the API is unavailable.
  });
}

function setPremappedDemo(exercise) {
  const iframe = $("#premappedDemoFrameVideo");
  const title = $("#premappedDemoTitle");
  const source = $("#premappedDemoSource");
  if (!iframe || !title || !source) return;

  referenceCandidates = getReferenceCandidates(exercise);
  referenceLoadSerial++;
  referenceCandidateIndex = -1;
  referencePlayerExerciseId = exercise?.id || "";
  destroyReferenceProbe();

  title.textContent = exercise?.name
    ? `${exercise.name} Demo`
    : "Exercise Demo";

  if (!referenceCandidates.length) {
    iframe.src = "about:blank";
    source.textContent = "Reference demonstration not mapped yet.";
    return;
  }

  loadReferenceCandidate(0);
}


const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

function showView(name, options = {}) {
  const pushHistory = options.pushHistory !== false;

  $$(".view").forEach(v =>
    v.classList.remove("active-view")
  );

  const target = $(`#${name}View`);
  if (target) target.classList.add("active-view");

  $$(".nav-item").forEach(b =>
    b.classList.toggle(
      "active",
      b.dataset.view === name
    )
  );

  const titles = {
    home: "Train with better form.",
    recommend: "Build your workout.",
    meal: "Eat smarter for your goal.",
    winterArc: "Build your winter arc.",
    library: "Choose your movement.",
    form: "Practice with better form.",
    history: "My workout history."
  };

  $("#pageTitle").textContent =
    titles[name] || "FORMFIT AI";

  if (name === "history") {
    loadHistory();
  }

  if (pushHistory) {
    const hash = name === "home" ? "" : `#${name}`;
    history.pushState({ view: name }, "", `${location.pathname}${hash}`);
  }
}

function bindInternalBackNavigation() {
  const valid = new Set([
    "home",
    "recommend",
    "meal",
    "library",
    "form",
    "history"
  ]);

  const initial = valid.has(location.hash.slice(1))
    ? location.hash.slice(1)
    : "home";

  history.replaceState(
    { view: initial },
    "",
    `${location.pathname}${initial === "home" ? "" : `#${initial}`}`
  );

  window.addEventListener("popstate", (event) => {
    const view =
      event.state?.view ||
      (valid.has(location.hash.slice(1))
        ? location.hash.slice(1)
        : "home");

    showView(view, { pushHistory: false });
  });

  showView(initial, { pushHistory: false });
}


function bindAccountLogout() {
  const btn = $("#logoutBtn");
  if (!btn || btn.dataset.bound === "1") return;

  btn.dataset.bound = "1";

  btn.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store"
      });
    } catch (_) {}

    try {
      if (typeof stopFormSession === "function") {
        stopFormSession();
      }
    } catch (_) {}

    const email = $("#accountEmail");
    const avatar = $("#accountAvatar");

    if (email) email.textContent = "Not signed in";
    if (avatar) avatar.textContent = "U";

    showView("home");

    const overlay = $("#authOverlay");
    if (overlay) {
      overlay.classList.add("visible");
      overlay.setAttribute("aria-hidden", "false");
    }
  });
}

function bindNavigation() {
  bindAccountLogout();
  $$("[data-view]").forEach(btn => {
    btn.addEventListener("click", () =>
      showView(btn.dataset.view)
    );
  });

  $("#quickAI").onclick = () =>
    showView("recommend");

  $("#quickLibrary").onclick = () =>
    showView("library");

  const endSessionBtn = $("#endSessionBtn");
  if (endSessionBtn) {
    endSessionBtn.onclick = endAndSaveFormSession;
  }

  const refreshHistory = $("#refreshHistory");
  if (refreshHistory) {
    refreshHistory.onclick = loadHistory;
  }

  const historyNav = document.querySelector('[data-view="history"]');
  if (historyNav) {
    historyNav.addEventListener("click", () => {
      loadHistory();
    });
  }
}


/* ============================================================
   FORMFIT — WINTER ARC
   Seasonal goal-setting layer. Uses existing workout + diet builders.
   Does not touch pose/model logic.
   ============================================================ */

const winterArcState = {
  equipment: []
};

function winterArcDaysBetween(start, end) {
  const a = new Date(start + "T00:00:00");
  const b = new Date(end + "T00:00:00");
  return Math.max(1, Math.ceil((b - a) / 86400000) + 1);
}

function syncWinterArcDays() {
  const start = new Date();
  const year = start.getFullYear();
  // Winter Arc is commonly framed as Oct 1 → Jan 1. If a user opens
  // FormFit during Oct–Dec, keep the current season; Jan–Sep points
  // to the next upcoming Oct 1.
  const arcYear = start.getMonth() >= 9 ? year : year + 1;
  const arcStart = `${arcYear}-10-01`;
  const nextYear = arcYear + 1;
  const arcEnd = `${nextYear}-01-01`;
  const days = winterArcDaysBetween(arcStart, arcEnd);
  const el = $("#winterArcDays");
  if (el) el.textContent = days;
  return { arcStart, arcEnd, days };
}

function winterArcGoalDietMap(goal) {
  if (goal === "fat loss") return "cutting";
  if (goal === "muscle gain") return "muscle_gain";
  if (goal === "strength") return "muscle_gain";
  if (goal === "mobility") return "maintaining";
  return "maintaining";
}

function winterArcReasonText(reason) {
  return {
    physique: "physique improvement",
    strength: "strength development",
    consistency: "consistency and routine",
    fitness: "stamina and overall fitness",
    sport: "sport/performance support"
  }[reason] || "personal improvement";
}

function renderWinterArcResult(profile, habits, dates) {
  const result = $("#winterArcResult");
  if (!result) return;
  const habitLabels = {
    training: "training / active recovery",
    protein: "nutrition target",
    steps: "daily movement",
    sleep: "sleep routine",
    screen: "screen-free / reading block"
  };
  result.innerHTML = `
    <div class="winter-plan-head">
      <div>
        <span class="eyebrow">YOUR WINTER ARC</span>
        <h3>${escapeHtml(profile.goalLabel)} • ${escapeHtml(profile.splitLabel)}</h3>
        <p>${dates.arcStart} → ${dates.arcEnd} • ${dates.days} days • Built around ${escapeHtml(winterArcReasonText(profile.reason))}.</p>
      </div>
      <div class="winter-score-box"><span>ACTIVE RULES</span><strong>${habits.length}</strong></div>
    </div>
    <div class="winter-output-grid">
      <article class="winter-output-card"><span class="eyebrow">TRAINING</span><h4>Smart workout direction</h4><p>${escapeHtml(profile.trainingNote)}</p><button type="button" class="secondary-btn" id="winterBuildWorkout">Build Winter Workout →</button></article>
      <article class="winter-output-card"><span class="eyebrow">NUTRITION</span><h4>Arc food direction</h4><p>${escapeHtml(profile.dietNote)}</p><button type="button" class="secondary-btn" id="winterBuildDiet">Build Winter Diet →</button></article>
      <article class="winter-output-card"><span class="eyebrow">DAILY CHECKLIST</span><h4>Keep these visible</h4><p>${habits.map(x => escapeHtml(habitLabels[x] || x)).join(" • ")}</p></article>
    </div>
    <div class="winter-arc-note"><strong>Remember:</strong> Winter Arc is a consistency framework, not a punishment challenge. Missing one day is a signal to resume—not a reason to restart from zero.</div>
  `;

  $("#winterBuildWorkout")?.addEventListener("click", async () => {
    showView("recommend");
    const goalBtn = $$(".choice[data-field='goal']").find(b => b.dataset.value === profile.goal);
    if (goalBtn) goalBtn.click();
    const split = $("#workoutSplit");
    if (split) { split.value = profile.split; split.dispatchEvent(new Event("change")); }
    $("#days").value = profile.days;
    $("#perDay").value = Math.min(10, Math.max(3, profile.minutes >= 70 ? 7 : profile.minutes >= 50 ? 6 : 5));
    state.equipment = [...profile.equipment];
    $$("#equipmentChoices .choice").forEach(btn => btn.classList.toggle("selected", state.equipment.includes(btn.dataset.value)));
    await generatePlan({preventDefault() {}});
  });

  $("#winterBuildDiet")?.addEventListener("click", () => {
    showView("meal");
    $("#mealAge")?.focus();
    const goal = winterArcGoalDietMap(profile.goal);
    const pref = profile.preference;
    $$("#mealGoalChoices .meal-choice").forEach(btn => btn.classList.toggle("selected", btn.dataset.value === goal));
    $$("#mealPreferenceChoices .meal-choice").forEach(btn => btn.classList.toggle("selected", btn.dataset.value === pref));
    mealState.goal = goal;
    mealState.preference = pref;
    const note = $("#dietStyleNote");
    if (note) note.value = `Winter Arc: ${winterArcReasonText(profile.reason)}`;
  });
}

function bindWinterArc() {
  syncWinterArcDays();
  $$("[data-winter-equipment]").forEach(btn => {
    btn.addEventListener("click", () => {
      const value = btn.dataset.winterEquipment;
      if (winterArcState.equipment.includes(value)) {
        winterArcState.equipment = winterArcState.equipment.filter(x => x !== value);
        btn.classList.remove("selected");
      } else {
        winterArcState.equipment.push(value);
        btn.classList.add("selected");
      }
    });
  });

  const form = $("#winterArcForm");
  if (!form) return;
  form.addEventListener("submit", event => {
    event.preventDefault();
    const days = Number($("#winterDays")?.value || 4);
    const minutes = Number($("#winterMinutes")?.value || 60);
    if (!winterArcState.equipment.length) {
      alert("Select at least one equipment option. FormFit will not assume Bodyweight.");
      return;
    }
    const goal = $("#winterGoal")?.value || "muscle gain";
    const reason = $("#winterReason")?.value || "physique";
    const split = $("#winterSplit")?.value || "auto";
    const splitLabels = {
      auto: "FormFit-decided split",
      push_pull_legs: "Push • Pull • Legs",
      full_body: "Full Body",
      upper_lower: "Upper • Lower",
      one_body_part: "One body part a day",
      bro_split: "Chest • Back • Shoulders • Arms • Legs"
    };
    const dates = syncWinterArcDays();
    const habits = $$('input[name="winterHabit"]:checked').map(x => x.value);
    const preference = $("#winterDietPreference")?.value || "vegetarian";

    const trainingNote = split === "push_pull_legs"
      ? "Prioritize a repeatable PPL sequence, put the main compound movements first, then accessories, and keep weekly volume recoverable."
      : "Use the selected split as the structure, then prioritize goal-relevant compounds followed by targeted accessory work and manageable conditioning.";
    const dietNote = goal === "fat loss"
      ? "Use a sustainable calorie-controlled pattern with protein-rich meals, vegetables, whole foods and enough food to train well."
      : goal === "muscle gain" || goal === "strength"
        ? "Use a protein-focused meal pattern with sufficient energy, carbohydrates around training and foods you actually enjoy eating consistently."
        : "Use a balanced, repeatable meal pattern that supports training, recovery and your normal routine.";

    localStorage.setItem("formfit_winter_arc", JSON.stringify({dates, goal, reason, split, days, minutes, preference, equipment: winterArcState.equipment, habits}));
    renderWinterArcResult({
      goalLabel: {"muscle gain":"Muscle Gain", strength:"Strength", "fat loss":"Fat Loss", "general fitness":"General Fitness", mobility:"Mobility"}[goal] || goal,
      reason,
      split,
      splitLabel: splitLabels[split] || split,
      days,
      minutes,
      preference,
      equipment: winterArcState.equipment,
      trainingNote,
      dietNote
    }, habits, dates);
  });
}

/* ============================================================
   FORMFIT — PERSONALIZED COUNTRY-BASED MEAL PLAN
   UI + approximate nutrition only. Does not touch pose/model code.
   ============================================================ */

const mealState = {
  goal: "bulking",
  preference: "vegetarian",
  country: (() => { try { return localStorage.getItem("formfit_country") || "IN"; } catch (_) { return "IN"; } })()
};
const COUNTRY_LABELS = {IN:"India",US:"United States",GB:"United Kingdom",CA:"Canada",AU:"Australia",AE:"UAE",DE:"Germany",JP:"Japan",MX:"Mexico",BR:"Brazil",FR:"France",IT:"Italy",ES:"Spain",CN:"China",KR:"South Korea",TH:"Thailand",ID:"Indonesia",TR:"Turkey",GR:"Greece",EG:"Egypt",ZA:"South Africa",NG:"Nigeria",PK:"Pakistan",BD:"Bangladesh",NP:"Nepal",LK:"Sri Lanka",PH:"Philippines",VN:"Vietnam",RU:"Russia",OTHER:"International"};
const COUNTRY_MEAL_FOOD = {
 US:{breakfast:[["Greek yogurt",200,"g",146,20,8,4],["Oatmeal",60,"g",228,7.8,38,4.2],["Banana",1,"medium",105,1.3,27,.4]],lunch:[["Whole-grain sandwich",1,"serving",380,25,45,12],["Chicken breast",120,"g cooked",198,37,0,4.3],["Mixed salad",200,"g",55,2,11,.5]],dinner:[["Brown rice",180,"g cooked",216,5,45,1.8],["Salmon",120,"g cooked",247,26,0,15],["Broccoli",200,"g",68,5.6,13,.8]]},
 GB:{breakfast:[["Porridge oats",60,"g",228,7.8,38,4.2],["Milk",250,"ml",150,8,12,8],["Berries",100,"g",50,1,12,.3]],lunch:[["Jacket potato",1,"medium",220,5,50,.2],["Tuna",120,"g",140,31,0,1],["Side salad",150,"g",40,2,7,.4]],dinner:[["Chicken",120,"g cooked",198,37,0,4.3],["Potatoes",200,"g",154,4,35,.2],["Green beans",150,"g",47,2.7,10,.3]]},
 CA:{breakfast:[["Oatmeal",60,"g",228,7.8,38,4.2],["Greek yogurt",200,"g",146,20,8,4],["Blueberries",100,"g",57,.7,14,.3]],lunch:[["Turkey wrap",1,"serving",360,28,40,10],["Carrot sticks",100,"g",41,.9,10,.2],["Apple",1,"medium",95,.5,25,.3]],dinner:[["Salmon",120,"g cooked",247,26,0,15],["Quinoa",180,"g cooked",216,8,39,3.5],["Vegetables",200,"g",80,4,15,1]]},
 AU:{breakfast:[["Weet-Bix",3,"biscuits",180,5,34,1],["Milk",250,"ml",150,8,12,8],["Banana",1,"medium",105,1.3,27,.4]],lunch:[["Chicken salad bowl",1,"serving",390,35,35,12],["Wholegrain bread",2,"slices",180,8,32,2]],dinner:[["Lean beef",120,"g cooked",250,32,0,12],["Sweet potato",200,"g",180,3.5,41,.3],["Broccoli",150,"g",51,4.2,10,.6]]},
 AE:{breakfast:[["Eggs",2,"eggs",144,12.6,.8,9.6],["Whole-wheat khubz",1,"piece",170,6,34,1.5],["Cucumber",100,"g",15,.7,3.6,.1]],lunch:[["Chicken shawarma bowl",1,"serving",420,35,45,12],["Hummus",60,"g",166,5,14,9]],dinner:[["Grilled fish",150,"g",220,32,0,9],["Rice",180,"g cooked",234,4.9,51,.5],["Salad",200,"g",55,2,11,.5]]},
 DE:{breakfast:[["Muesli",60,"g",230,7,40,5],["Skyr",200,"g",126,22,8,.4],["Apple",1,"medium",95,.5,25,.3]],lunch:[["Rye bread",2,"slices",190,6,36,2],["Turkey",120,"g",160,34,0,2],["Salad",150,"g",40,2,7,.4]],dinner:[["Potatoes",200,"g",154,4,35,.2],["Quark",200,"g",136,24,8,.4],["Vegetables",200,"g",80,4,15,1]]},
 JP:{breakfast:[["Rice",150,"g cooked",195,4,42,.5],["Egg",1,"egg",72,6.3,.4,4.8],["Miso soup",1,"bowl",40,3,5,1]],lunch:[["Chicken rice bowl",1,"serving",420,32,55,8],["Edamame",100,"g",121,12,9,5]],dinner:[["Salmon",120,"g",247,26,0,15],["Rice",150,"g cooked",195,4,42,.5],["Steamed vegetables",200,"g",70,4,13,.8]]},
MX:{breakfast:[["Huevos rancheros",1,"serving",320,18,35,12],["Papaya",150,"g",65,1,16,.2]],lunch:[["Chicken fajita bowl",1,"serving",430,34,48,12],["Black beans",120,"g",132,9,24,.5]],dinner:[["Fish tacos",2,"tacos",380,28,42,12],["Avocado",70,"g",112,1.4,6,10]]},
BR:{breakfast:[["Tapioca crepe",1,"serving",220,3,38,6],["Papaya",150,"g",65,1,16,.2]],lunch:[["Rice and beans",1,"plate",410,14,72,8],["Grilled chicken",120,"g",198,37,0,4.3]],dinner:[["Beef stroganoff",1,"serving",420,30,20,24],["Salad",200,"g",55,2,11,.5]]},
FR:{breakfast:[["Wholegrain baguette",100,"g",270,9,55,2],["Yogurt",150,"g",92,8,10,3]],lunch:[["Lentil salad",1,"bowl",300,18,42,8],["Roast chicken",120,"g",198,37,0,4.3]],dinner:[["Ratatouille",1,"serving",180,5,24,7],["Fish fillet",150,"g",220,32,0,9]]},
IT:{breakfast:[["Wholegrain toast",2,"slices",180,7,32,3],["Cappuccino",1,"cup",110,6,10,5]],lunch:[["Pasta with tomato",1,"plate",380,13,68,7],["White beans",120,"g",140,9,25,.5]],dinner:[["Grilled fish",150,"g",220,32,0,9],["Roasted vegetables",200,"g",120,4,18,4]]},
ES:{breakfast:[["Tomato toast",2,"slices",240,8,38,7],["Orange",1,"medium",62,1,15,.2]],lunch:[["Paella",1,"plate",430,28,55,12],["Gazpacho",1,"bowl",90,3,14,3]],dinner:[["Tortilla española",1,"serving",320,14,28,17],["Green salad",150,"g",40,2,7,.4]]},
CN:{breakfast:[["Congee",1,"bowl",180,6,32,3],["Boiled egg",1,"egg",72,6.3,.4,4.8]],lunch:[["Chicken stir-fry",1,"plate",390,32,42,12],["Steamed rice",150,"g",195,4,42,.5]],dinner:[["Tofu and vegetables",1,"serving",280,18,22,12],["Rice",150,"g cooked",195,4,42,.5]]},
KR:{breakfast:[["Rice",150,"g cooked",195,4,42,.5],["Egg",1,"egg",72,6.3,.4,4.8]],lunch:[["Bibimbap",1,"bowl",480,22,65,15],["Kimchi",80,"g",20,1,4,.2]],dinner:[["Grilled fish",150,"g",220,32,0,9],["Rice",150,"g cooked",195,4,42,.5]]},
TH:{breakfast:[["Thai omelette",1,"serving",260,15,5,19],["Fruit",150,"g",80,1,20,.3]],lunch:[["Chicken pad thai",1,"plate",450,28,58,14],["Papaya salad",1,"bowl",120,3,20,4]],dinner:[["Tom yum soup",1,"bowl",180,20,10,7],["Rice",150,"g cooked",195,4,42,.5]]},
ID:{breakfast:[["Nasi uduk",1,"serving",350,9,48,14],["Egg",1,"egg",72,6.3,.4,4.8]],lunch:[["Gado-gado",1,"plate",360,16,35,18],["Rice",150,"g cooked",195,4,42,.5]],dinner:[["Grilled chicken",120,"g",198,37,0,4.3],["Tempeh",100,"g",195,20,8,11]]},
TR:{breakfast:[["Menemen",1,"serving",260,14,14,16],["Wholegrain bread",2,"slices",180,8,32,2]],lunch:[["Lentil soup",1,"bowl",210,13,32,4],["Bulgur",180,"g cooked",150,5,34,.5]],dinner:[["Chicken kebab",150,"g",250,40,2,9],["Shepherd salad",200,"g",70,3,12,2]]},
GR:{breakfast:[["Greek yogurt",200,"g",146,20,8,4],["Honey",15,"g",46,0,12,0]],lunch:[["Greek salad",1,"bowl",260,9,18,17],["Chickpeas",150,"g",246,13,41,4]],dinner:[["Grilled fish",150,"g",220,32,0,9],["Potatoes",200,"g",154,4,35,.2]]},
EG:{breakfast:[["Ful medames",1,"bowl",280,16,38,8],["Pita",1,"piece",170,6,34,1.5]],lunch:[["Koshari",1,"plate",520,18,88,12],["Salad",150,"g",40,2,7,.4]],dinner:[["Grilled chicken",150,"g",248,46,0,5.4],["Rice",150,"g cooked",195,4,42,.5]]},
ZA:{breakfast:[["Mabele porridge",1,"bowl",240,7,42,5],["Banana",1,"medium",105,1.3,27,.4]],lunch:[["Chicken stew",1,"serving",360,32,28,14],["Pap",180,"g",190,4,42,1]],dinner:[["Bean stew",1,"bowl",260,15,42,4],["Roasted vegetables",200,"g",120,4,18,4]]},
NG:{breakfast:[["Akara",3,"pieces",300,12,28,16],["Pap",1,"bowl",180,4,34,3]],lunch:[["Jollof rice",1,"plate",430,12,66,13],["Grilled chicken",120,"g",198,37,0,4.3]],dinner:[["Bean porridge",1,"bowl",320,17,48,7],["Plantain",150,"g",183,2,47,.5]]},
PK:{breakfast:[["Paratha",1,"piece",260,6,38,10],["Egg",1,"egg",72,6.3,.4,4.8]],lunch:[["Chicken karahi",1,"serving",360,32,12,22],["Roti",2,"medium",200,7,40,3]],dinner:[["Daal",1,"cup",180,10,30,3],["Rice",180,"g cooked",234,4.9,51,.5]]},
BD:{breakfast:[["Chira with milk",1,"bowl",300,10,48,8],["Banana",1,"medium",105,1.3,27,.4]],lunch:[["Rice and fish curry",1,"plate",430,28,58,12],["Lentils",1,"cup",180,10,30,3]],dinner:[["Chicken bhuna",1,"serving",350,32,12,20],["Rice",150,"g cooked",195,4,42,.5]]},
NP:{breakfast:[["Chiura",80,"g",300,6,62,3],["Curd",150,"g",92,5.3,6.8,4.5]],lunch:[["Dal bhat",1,"plate",450,17,78,8],["Vegetable tarkari",1,"serving",120,4,18,4]],dinner:[["Momo",8,"pieces",360,18,48,11],["Soup",1,"bowl",90,5,12,2]]},
LK:{breakfast:[["String hoppers",5,"pieces",260,6,52,3],["Dhal curry",1,"serving",180,10,25,5]],lunch:[["Rice and curry",1,"plate",450,18,70,12],["Fish curry",120,"g",220,28,4,10]],dinner:[["Chicken curry",150,"g",280,34,8,13],["Rice",150,"g cooked",195,4,42,.5]]},
PH:{breakfast:[["Pandesal",2,"pieces",220,7,40,4],["Egg",1,"egg",72,6.3,.4,4.8]],lunch:[["Chicken adobo",1,"serving",360,34,18,18],["Rice",180,"g cooked",234,4.9,51,.5]],dinner:[["Sinigang",1,"bowl",240,25,12,10],["Rice",150,"g cooked",195,4,42,.5]]},
VN:{breakfast:[["Pho",1,"bowl",350,24,48,8],["Fruit",150,"g",80,1,20,.3]],lunch:[["Banh mi",1,"sandwich",390,22,48,12],["Fresh spring rolls",2,"pieces",160,8,24,4]],dinner:[["Grilled pork",120,"g",280,30,8,15],["Rice",150,"g cooked",195,4,42,.5]]},
RU:{breakfast:[["Buckwheat porridge",1,"bowl",240,8,42,5],["Cottage cheese",150,"g",145,25,5,3]],lunch:[["Borscht",1,"bowl",180,8,24,6],["Rye bread",2,"slices",190,6,36,2]],dinner:[["Chicken cutlet",150,"g",300,32,12,15],["Potatoes",200,"g",154,4,35,.2]]}
};

const dietMemory = {
  favorite_foods: [],
  disliked_foods: [],
  avoid_foods: [],
  favorite_meals: [],
  notes: []
};

let activeDietPlan = null;
let activeDietProfile = null;
let savedDietCache = [];

const MEAL_GOALS = {
  bulking: {
    label: "Bulking",
    calorieFactor: 1.15,
    proteinPerKg: 1.8,
    description: "Calorie-surplus style plan with higher calories, protein and carbohydrates."
  },
  muscle_gain: {
    label: "Muscle Gain",
    calorieFactor: 1.08,
    proteinPerKg: 1.8,
    description: "Balanced high-protein plan with sufficient calories and carbohydrates."
  },
  cutting: {
    label: "Cutting",
    calorieFactor: 0.86,
    proteinPerKg: 2.0,
    description: "Controlled calories with high protein, vegetables and filling foods."
  },
  muscle_loss: {
    label: "Muscle Loss",
    calorieFactor: 0.80,
    proteinPerKg: 2.0,
    description: "Calorie-deficit oriented plan while keeping protein relatively high."
  },
  maintaining: {
    label: "Maintaining",
    calorieFactor: 1.00,
    proteinPerKg: 1.6,
    description: "Balanced maintenance-style intake for everyday eating."
  }
};

const MEAL_FOOD = {
  vegetarian: {
    breakfast: [
      ["Oats", 60, "g", 228, 7.8, 38.0, 4.2],
      ["Milk", 250, "ml", 150, 8.0, 12.0, 8.0],
      ["Banana", 1, "medium", 105, 1.3, 27.0, 0.4],
      ["Peanut butter", 15, "g", 90, 3.8, 3.0, 7.5]
    ],
    mid: [
      ["Curd", 200, "g", 122, 7.0, 9.0, 6.0],
      ["Apple", 1, "medium", 95, 0.5, 25.0, 0.3]
    ],
    lunch: [
      ["Roti", 3, "medium", 300, 10.0, 60.0, 5.0],
      ["Dal", 1, "cup", 180, 10.0, 30.0, 3.0],
      ["Paneer", 80, "g", 212, 14.5, 4.0, 15.5],
      ["Mixed vegetables", 200, "g", 100, 4.0, 18.0, 2.0],
      ["Curd", 150, "g", 92, 5.3, 6.8, 4.5]
    ],
    evening: [
      ["Roasted peanuts", 30, "g", 170, 7.5, 5.0, 14.5],
      ["Buttermilk", 250, "ml", 70, 4.0, 8.0, 2.0]
    ],
    dinner: [
      ["Rice", 180, "g cooked", 234, 4.9, 51.0, 0.5],
      ["Rajma", 1, "cup", 215, 13.0, 39.0, 1.5],
      ["Paneer", 60, "g", 159, 10.9, 3.0, 11.6],
      ["Salad", 200, "g", 55, 2.0, 11.0, 0.5]
    ],
    bedtime: [
      ["Milk", 200, "ml", 120, 6.4, 9.6, 6.4]
    ]
  },
  egg: {
    breakfast: [
      ["Oats", 60, "g", 228, 7.8, 38.0, 4.2],
      ["Milk", 250, "ml", 150, 8.0, 12.0, 8.0],
      ["Banana", 1, "medium", 105, 1.3, 27.0, 0.4],
      ["Peanut butter", 15, "g", 90, 3.8, 3.0, 7.5]
    ],
    mid: [
      ["Boiled eggs", 2, "eggs", 144, 12.6, 0.8, 9.6],
      ["Guava", 1, "medium", 68, 2.6, 14.0, 1.0]
    ],
    lunch: [
      ["Roti", 3, "medium", 300, 10.0, 60.0, 5.0],
      ["Dal", 1, "cup", 180, 10.0, 30.0, 3.0],
      ["Eggs", 2, "eggs", 144, 12.6, 0.8, 9.6],
      ["Mixed vegetables", 200, "g", 100, 4.0, 18.0, 2.0],
      ["Curd", 150, "g", 92, 5.3, 6.8, 4.5]
    ],
    evening: [
      ["Poha", 180, "g cooked", 230, 5.5, 38.0, 6.0],
      ["Peanuts", 15, "g", 85, 3.8, 2.5, 7.2]
    ],
    dinner: [
      ["Rice", 180, "g cooked", 234, 4.9, 51.0, 0.5],
      ["Dal", 1, "cup", 180, 10.0, 30.0, 3.0],
      ["Egg bhurji", 3, "eggs", 216, 18.9, 1.2, 14.4],
      ["Salad", 200, "g", 55, 2.0, 11.0, 0.5]
    ],
    bedtime: [
      ["Milk", 200, "ml", 120, 6.4, 9.6, 6.4]
    ]
  },
  non_vegetarian: {
    breakfast: [
      ["Oats", 60, "g", 228, 7.8, 38.0, 4.2],
      ["Milk", 250, "ml", 150, 8.0, 12.0, 8.0],
      ["Banana", 1, "medium", 105, 1.3, 27.0, 0.4],
      ["Peanut butter", 15, "g", 90, 3.8, 3.0, 7.5]
    ],
    mid: [
      ["Boiled eggs", 2, "eggs", 144, 12.6, 0.8, 9.6],
      ["Apple", 1, "medium", 95, 0.5, 25.0, 0.3]
    ],
    lunch: [
      ["Roti", 3, "medium", 300, 10.0, 60.0, 5.0],
      ["Dal", 1, "cup", 180, 10.0, 30.0, 3.0],
      ["Chicken", 120, "g cooked", 198, 37.0, 0.0, 4.3],
      ["Mixed vegetables", 200, "g", 100, 4.0, 18.0, 2.0],
      ["Curd", 150, "g", 92, 5.3, 6.8, 4.5]
    ],
    evening: [
      ["Roasted chana", 40, "g", 160, 8.0, 24.0, 2.5],
      ["Buttermilk", 250, "ml", 70, 4.0, 8.0, 2.0]
    ],
    dinner: [
      ["Rice", 180, "g cooked", 234, 4.9, 51.0, 0.5],
      ["Dal", 1, "cup", 180, 10.0, 30.0, 3.0],
      ["Chicken", 120, "g cooked", 198, 37.0, 0.0, 4.3],
      ["Salad", 200, "g", 55, 2.0, 11.0, 0.5]
    ],
    bedtime: [
      ["Milk", 200, "ml", 120, 6.4, 9.6, 6.4]
    ]
  }
};

const MEAL_LABELS = {
  breakfast: "BREAKFAST",
  mid: "MID-MORNING SNACK",
  lunch: "LUNCH",
  evening: "EVENING SNACK",
  dinner: "DINNER",
  bedtime: "BEDTIME SNACK"
};

function mealAgeFactor(age) {
  if (age <= 25) return 1.05;
  if (age <= 35) return 1.00;
  if (age <= 50) return 0.95;
  return 0.90;
}

function round1(n) { return Math.round(n * 10) / 10; }
function round0(n) { return Math.round(n); }

function mealBasePlan(preference, country = mealState.country) {
  const foods = COUNTRY_MEAL_FOOD[country] ? { ...MEAL_FOOD[preference], ...COUNTRY_MEAL_FOOD[country] } : MEAL_FOOD[preference];
  return Object.keys(MEAL_LABELS).map(key => ({
    key,
    name: MEAL_LABELS[key],
    items: foods[key].map(x => [...x])
  }));
}

function scaleMealPlan(plan, calorieTarget, proteinTarget) {
  const baseCalories = plan.reduce(
    (sum, meal) => sum + meal.items.reduce((s, x) => s + x[3], 0), 0
  );
  const baseProtein = plan.reduce(
    (sum, meal) => sum + meal.items.reduce((s, x) => s + x[4], 0), 0
  );

  // First scale to calories, then use a small protein-preserving adjustment.
  const scale = Math.max(0.68, Math.min(1.38, calorieTarget / baseCalories));
  const proteinNeedFactor = Math.max(0.92, Math.min(1.12, proteinTarget / (baseProtein * scale)));

  return plan.map(meal => ({
    ...meal,
    items: meal.items.map(x => {
      const quantity = typeof x[1] === "number" ? round1(x[1] * scale) : x[1];
      return {
        food: x[0],
        quantity,
        unit: x[2],
        calories: round0(x[3] * scale),
        protein: round1(x[4] * scale * proteinNeedFactor),
        carbs: round1(x[5] * scale),
        fat: round1(x[6] * scale)
      };
    })
  }));
}

function dietListHas(list, food) {
  const name = String(food || "").trim().toLowerCase();
  return (list || []).some(x => {
    const value = String(x || "").trim().toLowerCase();
    return value && (name === value || name.includes(value) || value.includes(name));
  });
}

function dietFoodScore(food) {
  let score = 0;
  if (dietListHas(dietMemory.favorite_foods, food)) score += 5;
  if (dietListHas(dietMemory.disliked_foods, food)) score -= 8;
  if (dietListHas(dietMemory.avoid_foods, food)) score -= 100;
  return score;
}

function mealItemFromBase(x) {
  return {
    food: x[0],
    quantity: typeof x[1] === "number" ? x[1] : x[1],
    unit: x[2],
    calories: Number(x[3] || 0),
    protein: Number(x[4] || 0),
    carbs: Number(x[5] || 0),
    fat: Number(x[6] || 0),
    baseQuantity: typeof x[1] === "number" ? x[1] : null
  };
}

function chooseDietAlternative(mealKey, currentFood, preference, usedFoods = new Set()) {
  const source = (MEAL_FOOD[preference]?.[mealKey] || []).map(mealItemFromBase);
  const all = [...source];
  const candidates = all.filter(item =>
    item.food.toLowerCase() !== String(currentFood || "").toLowerCase() &&
    !usedFoods.has(item.food.toLowerCase()) &&
    !dietListHas(dietMemory.disliked_foods, item.food) &&
    !dietListHas(dietMemory.avoid_foods, item.food)
  );

  candidates.sort((a, b) => dietFoodScore(b.food) - dietFoodScore(a.food));
  return candidates[0] || null;
}

function personalizeMealPlan(plan, preference) {
  const next = plan.map(meal => ({
    ...meal,
    items: meal.items.map(item => ({ ...item }))
  }));

  for (const meal of next) {
    const used = new Set(meal.items.map(x => String(x.food).toLowerCase()));
    meal.items = meal.items.map(item => {
      if (!dietListHas(dietMemory.disliked_foods, item.food) &&
          !dietListHas(dietMemory.avoid_foods, item.food)) {
        return item;
      }

      const replacement = chooseDietAlternative(meal.key, item.food, preference, used);
      if (!replacement) return item;

      used.delete(String(item.food).toLowerCase());
      used.add(String(replacement.food).toLowerCase());
      const scale = typeof replacement.quantity === "number" && replacement.quantity > 0
        ? (typeof item.quantity === "number" ? item.quantity / replacement.quantity : 1)
        : 1;

      return {
        ...replacement,
        quantity: typeof replacement.quantity === "number"
          ? round1(replacement.quantity * scale)
          : replacement.quantity,
        calories: round0(replacement.calories * scale),
        protein: round1(replacement.protein * scale),
        carbs: round1(replacement.carbs * scale),
        fat: round1(replacement.fat * scale),
        baseQuantity: replacement.baseQuantity
      };
    });
  }

  // Put stronger favorites first without disturbing the meal structure.
  for (const meal of next) {
    meal.items.sort((a, b) => dietFoodScore(b.food) - dietFoodScore(a.food));
  }
  return next;
}

function recalculateDietPlan(plan) {
  return (plan || []).map(meal => ({
    ...meal,
    items: (meal.items || []).map(item => ({ ...item }))
  }));
}

function dietPlanTotals(plan) {
  return (plan || []).reduce((acc, meal) => {
    (meal.items || []).forEach(item => {
      acc.calories += Number(item.calories || 0);
      acc.protein += Number(item.protein || 0);
      acc.carbs += Number(item.carbs || 0);
      acc.fat += Number(item.fat || 0);
    });
    return acc;
  }, { calories: 0, protein: 0, carbs: 0, fat: 0 });
}

function dietEnergyEstimate(profile) {
  const activity = Number(profile.activity || 1.55);
  // Mifflin-St Jeor estimate when height and metabolic profile are supplied;
  // otherwise use a transparent weight/age fallback, never pretend it's exact.
  if (profile.height && profile.sex !== "unspecified") {
    const sexOffset = profile.sex === "male" ? 5 : -161;
    const bmr = (10 * profile.weight) + (6.25 * profile.height) - (5 * profile.age) + sexOffset;
    return Math.max(1200, bmr * activity);
  }
  return profile.weight * 30 * mealAgeFactor(profile.age) * activity / 1.55;
}

function bodyFatEstimate(profile) {
  const {height, waist, neck, hip, sex} = profile;
  if (!height || !waist || !neck || sex === "unspecified") return null;
  // US Navy circumference estimate. Inputs must be centimeters; convert to inches.
  const cmToIn = n => n / 2.54;
  const w = cmToIn(waist), n = cmToIn(neck), h = cmToIn(height), hips = hip ? cmToIn(hip) : null;
  let pct;
  if (sex === "male" && w > n) pct = 86.010 * Math.log10(w - n) - 70.041 * Math.log10(h) + 36.76;
  else if (sex === "female" && hips && w + hips > n) pct = 163.205 * Math.log10(w + hips - n) - 97.684 * Math.log10(h) - 78.387;
  else return null;
  if (!Number.isFinite(pct) || pct < 2 || pct > 70) return null;
  return Math.round(pct * 10) / 10;
}

function dietHealthKnowledge(profile) {
  const raw = `${profile.diseases || ""} ${profile.healthNotes || ""}`.toLowerCase();
  const notes = [];
  const flags = [];
  const add = (key, note) => { flags.push(key); notes.push(note); };
  if (/diabet|prediabet|blood sugar/.test(raw)) add("glucose", "Blood-glucose condition noted: prefer consistent carbohydrate portions, fibre-rich foods and unsweetened drinks; individual medication and glucose needs vary.");
  if (/blood pressure|hypertension|high bp/.test(raw)) add("sodium", "Blood-pressure condition noted: favour less-salted, minimally processed foods. Sodium is not fully quantified in this food database, so this plan cannot certify a sodium limit.");
  if (/thyroid|hypothyroid|hyperthyroid/.test(raw)) add("thyroid", "Thyroid condition noted: use a balanced plan and follow clinician advice on medication timing and any specific restrictions; food alone does not treat thyroid disease.");
  if (/pcos|polycystic/.test(raw)) add("pcos", "PCOS noted: emphasize sustainable balanced meals, fibre and protein; there is no single universal PCOS diet.");
  if (/gout|uric acid/.test(raw)) add("gout", "Gout/high uric acid noted: avoid alcohol advice being inferred from this plan and seek individualized guidance on purines, hydration and medicines.");
  if (/anemi|iron deficiency/.test(raw)) add("anemia", "Anemia/iron deficiency noted: cause matters. Include varied iron-containing foods where suitable and follow clinician guidance; do not start supplements solely from this plan.");
  if (/celiac|coeliac|gluten/.test(raw)) add("gluten", "Possible gluten-related condition noted: this plan does not guarantee gluten-free preparation or cross-contamination control; verify every ingredient and label.");
  if (/kidney|renal|dialysis|liver|hepatic|cirrhosis/.test(raw)) add("specialist", "Kidney/liver condition noted: protein, potassium, sodium, fluids and other targets may require individualized clinical management. Treat this output as a general template only and get clinician/dietitian approval before following it.");
  if (/allerg|anaphyl|peanut|tree nut|milk allergy|egg allergy|fish allergy|shellfish/.test(raw)) add("allergy", "Allergy mentioned: list the exact allergen under Foods to Avoid and verify ingredients and cross-contact. This meal database cannot guarantee allergen-free food.");
  if (raw.trim() && !flags.length) notes.push("A health condition was entered but no condition-specific rule matched. FormFit will not invent a therapeutic diet; follow your clinician's advice and use this as a general meal template only.");
  return {notes, flags, hasCondition: !!raw.trim()};
}

function renderMealPlan(profile, suppliedPlan = null) {
  const goal = MEAL_GOALS[profile.goal] || MEAL_GOALS.bulking;
  const maintenanceKcal = dietEnergyEstimate(profile);
  // Avoid aggressive targets. Disease-specific clinical calorie/protein prescriptions are not guessed.
  const calorieTarget = Math.round(Math.max(1200, maintenanceKcal * goal.calorieFactor) / 50) * 50;
  const proteinTarget = Math.round(profile.weight * goal.proteinPerKg);
  const health = dietHealthKnowledge(profile);
  const estimatedBodyFat = bodyFatEstimate(profile);

  let plan;
  if (suppliedPlan) {
    plan = recalculateDietPlan(suppliedPlan);
  } else {
    plan = personalizeMealPlan(
      scaleMealPlan(
        mealBasePlan(profile.preference, profile.country),
        calorieTarget,
        proteinTarget
      ),
      profile.preference
    );
  }

  // Ensure every editable numeric item has a stable base quantity.
  plan.forEach(meal => meal.items.forEach(item => {
    if (item.baseQuantity == null && typeof item.quantity === "number") {
      item.baseQuantity = item.quantity;
    }
  }));

  activeDietPlan = plan;
  activeDietProfile = { ...profile };

  const totals = dietPlanTotals(plan);
  const preferenceLabel = {
    vegetarian: "Vegetarian",
    egg: "Egg",
    non_vegetarian: "Non-Vegetarian"
  }[profile.preference] || profile.preference;

  const result = $("#mealPlanResult");
  result.innerHTML = `
    <div class="meal-profile-card">
      <div>
        <span class="eyebrow">YOUR SMART PERSONALIZED PLAN</span>
        <h3>${escapeHtml(goal.label)} • ${escapeHtml(preferenceLabel)} • ${escapeHtml(COUNTRY_LABELS[profile.country] || "Local")}</h3>
        <small style="color:var(--muted)">${dietMemory.favorite_foods.length ? "Built around your learned food preferences." : "Start rating meals to teach FormFit your taste."}</small>
      </div>
      <div class="meal-profile-stats">
        <span><b>${profile.age}</b> Age</span>
        <span><b>${profile.weight} kg</b> Weight</span>
        ${profile.height ? `<span><b>${profile.height} cm</b> Height</span>` : ""}
        <span><b>~${round0(calorieTarget)}</b> kcal target</span>
        <span><b>~${proteinTarget} g</b> protein target</span>
      </div>
    </div>

    <div class="diet-intelligence-summary">
      <h4>Why this plan was built this way</h4>
      <p>Uses your age, weight, ${profile.height ? "height, " : ""}activity level, goal, food style, country and food exclusions. Energy needs are estimates, not measurements.</p>
      ${estimatedBodyFat !== null ? `<p><b>Estimated body fat:</b> ${estimatedBodyFat}% · estimated fat mass ${(profile.weight * estimatedBodyFat / 100).toFixed(1)} kg · estimated fat-free mass ${(profile.weight * (1 - estimatedBodyFat / 100)).toFixed(1)} kg.</p>` : (profile.waist || profile.neck || profile.hip ? `<p>Body-fat estimate unavailable: provide all measurements required for your selected profile.</p>` : "")}
      ${health.notes.map(n => `<p class="diet-health-note">${escapeHtml(n)}</p>`).join("")}
      ${health.hasCondition && health.flags.includes("specialist") ? `<p class="diet-health-warning"><b>Clinical review required:</b> FormFit cannot safely set disease-specific nutrition limits for kidney/liver conditions from a text label alone.</p>` : ""}
    </div>
    <div id="dietSwapSuggestions" class="diet-swap-suggestions" aria-live="polite"></div>

    <div class="meal-plan-grid">
      ${plan.map((meal, mealIndex) => `
        <article class="meal-card" data-meal-index="${mealIndex}">
          <div class="meal-card-head">
            <div>
              <span class="meal-number">${MEAL_LABELS[meal.key]}</span>
              <h3>${escapeHtml(meal.name)}</h3>
            </div>
            <span class="meal-kcal">~${meal.items.reduce((s,x)=>s+x.calories,0)} kcal</span>
          </div>
          <div class="meal-items">
            ${meal.items.map((item, itemIndex) => `
              <div class="meal-item" data-meal-index="${mealIndex}" data-item-index="${itemIndex}">
                <div>
                  <strong>${escapeHtml(item.food)}</strong>
                  <small>${item.quantity} ${escapeHtml(item.unit)}</small>
                </div>
                <div class="meal-item-macros">
                  <b>${round0(item.calories)} kcal</b>
                  <span>P ${round1(item.protein)}g</span>
                  <span>C ${round1(item.carbs)}g</span>
                  <span>F ${round1(item.fat)}g</span>
                </div>
                <div class="meal-card-actions">
                  <button type="button" class="meal-action-btn favorite ${dietListHas(dietMemory.favorite_foods, item.food) ? "active" : ""}" data-diet-action="favorite" data-food="${escapeHtml(item.food)}" data-meal="${escapeHtml(meal.key)}">♥ Favorite</button>
                  <button type="button" class="meal-action-btn dislike ${dietListHas(dietMemory.disliked_foods, item.food) ? "active" : ""}" data-diet-action="dislike" data-food="${escapeHtml(item.food)}" data-meal="${escapeHtml(meal.key)}">Not for me</button>
                  <button type="button" class="meal-action-btn" data-diet-action="replace" data-food="${escapeHtml(item.food)}" data-meal-index="${mealIndex}" data-item-index="${itemIndex}">↻ Replace</button>
                </div>
                ${typeof item.quantity === "number" ? `
                  <div class="meal-edit-row">
                    <label>Amount</label>
                    <input class="meal-qty-input" type="number" min="0.1" step="0.1" value="${item.quantity}" data-meal-index="${mealIndex}" data-item-index="${itemIndex}">
                    <span style="font-size:9px;color:#71888d">${escapeHtml(item.unit)}</span>
                    <button type="button" class="meal-qty-apply" data-diet-action="apply-quantity">Apply</button>
                  </div>` : ""}
              </div>
            `).join("")}
          </div>
          <div class="meal-total">
            <span>Meal total</span>
            <b>~${round0(meal.items.reduce((s,x)=>s+x.calories,0))} kcal</b>
            <span>Protein ${round1(meal.items.reduce((s,x)=>s+x.protein,0))}g</span>
          </div>
        </article>
      `).join("")}
    </div>

    <div class="daily-summary-card">
      <div>
        <span class="eyebrow">DAILY NUTRITION SUMMARY</span>
        <h3>Your current edited plan</h3>
        <p>${escapeHtml(goal.description)}</p>
      </div>
      <div class="daily-summary-grid">
        <div><span>Total Calories</span><strong>~${round0(totals.calories)} kcal</strong></div>
        <div><span>Total Protein</span><strong>~${round1(totals.protein)} g</strong></div>
        <div><span>Total Carbohydrates</span><strong>~${round1(totals.carbs)} g</strong></div>
        <div><span>Total Fat</span><strong>~${round1(totals.fat)} g</strong></div>
      </div>
      <div class="meal-save-bar">
        <small>Edits stay in this plan until you save it.</small>
        <button type="button" class="primary-btn" data-diet-action="save-plan">♡ Save this diet</button>
        <button type="button" class="ghost-btn" data-diet-action="favorite-plan">★ Save as favorite</button>
      </div>
    </div>

    <div class="meal-feedback-box">
      <label for="dietPlanComment">TEACH FORMFIT — COMMENT ON THIS PLAN</label>
      <div class="meal-feedback-row">
        <textarea id="dietPlanComment" placeholder="e.g. I loved paneer but I don't like oats. Please make breakfast lighter."></textarea>
        <button type="button" class="primary-btn" data-diet-action="comment">Save feedback</button>
      </div>
    </div>

    <div class="meal-disclaimer">
      Nutrition values are approximate and should be adjusted according to individual needs.
      For medical or clinical nutrition requirements, consult a qualified dietitian.
    </div>
  `;
}

async function loadDietMemory() {
  try {
    const response = await fetch("/api/diet/profile", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    Object.assign(dietMemory, data.profile || {});
    const map = {
      favorite_foods: "#dietFavoriteFoods",
      disliked_foods: "#dietDislikedFoods",
      avoid_foods: "#dietAvoidFoods"
    };
    Object.entries(map).forEach(([key, selector]) => {
      const el = $(selector);
      if (el) el.value = (dietMemory[key] || []).join(", ");
    });
    const note = $("#dietStyleNote");
    if (note) note.value = (dietMemory.notes || []).slice(-1)[0] || "";
    const status = $("#dietMemoryStatus");
    if (status) status.textContent = dietMemory.favorite_foods.length || dietMemory.disliked_foods.length ? "Personalized memory active" : "Ready to learn";
  } catch (_) {}
}

async function saveDietMemoryFromInputs(extraNote = "") {
  const profile = {
    favorite_foods: ($("#dietFavoriteFoods")?.value || "").split(",").map(x => x.trim()).filter(Boolean),
    disliked_foods: ($("#dietDislikedFoods")?.value || "").split(",").map(x => x.trim()).filter(Boolean),
    avoid_foods: ($( "#dietAvoidFoods")?.value || "").split(",").map(x => x.trim()).filter(Boolean),
    favorite_meals: dietMemory.favorite_meals || [],
    notes: [($("#dietStyleNote")?.value || "").trim(), extraNote.trim()].filter(Boolean)
  };
  try {
    const response = await fetch("/api/diet/profile", {
      method: "PUT",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(profile)
    });
    if (!response.ok) return false;
    const data = await response.json();
    Object.assign(dietMemory, data.profile || profile);
    return true;
  } catch (_) {
    return false;
  }
}

async function sendDietFeedback(foodName, mealKey, action, comment = "") {
  try {
    const response = await fetch("/api/diet/feedback", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ food_name: foodName || "general", meal_key: mealKey || "", action, comment })
    });
    if (!response.ok) return false;
    const data = await response.json();
    Object.assign(dietMemory, data.profile || dietMemory);
    return true;
  } catch (_) {
    return false;
  }
}

async function saveCurrentDietPlan(isFavorite = false) {
  if (!activeDietPlan || !activeDietProfile) return;
  const defaultName = `${MEAL_GOALS[activeDietProfile.goal]?.label || "Personalized"} • ${new Date().toLocaleDateString()}`;
  const name = window.prompt("Name this diet", defaultName);
  if (name === null) return;
  const response = await fetch("/api/diet/saved", {
    method: "POST",
    credentials: "same-origin",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: name.trim() || defaultName,
      is_favorite: isFavorite,
      plan: { profile: activeDietProfile, plan: activeDietPlan }
    })
  });
  if (!response.ok) {
    alert("Could not save this diet. Please make sure you are signed in.");
    return;
  }
  await loadSavedDiets();
  alert("Diet saved to your personal library.");
}

async function loadSavedDiets() {
  const list = $("#savedDietList");
  if (!list) return;
  try {
    const response = await fetch("/api/diet/saved", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) {
      list.innerHTML = `<div class="saved-diet-empty">Sign in to keep your saved diets across devices.</div>`;
      return;
    }
    const data = await response.json();
    savedDietCache = data.saved || [];
    if (!savedDietCache.length) {
      list.innerHTML = `<div class="saved-diet-empty">Generate a plan and save your favorite version here.</div>`;
      return;
    }
    list.innerHTML = savedDietCache.map(item => `
      <div class="saved-diet-item" data-saved-diet-id="${item.id}">
        <div>
          <strong>${item.is_favorite ? "★ " : ""}${escapeHtml(item.name)}</strong>
          <small>Updated ${escapeHtml(new Date(item.updated_at || item.created_at).toLocaleString())}</small>
        </div>
        <div class="saved-diet-actions">
          <button type="button" class="saved-diet-open" data-saved-action="open">Open</button>
          <button type="button" class="saved-diet-delete" data-saved-action="delete">Delete</button>
        </div>
      </div>
    `).join("");
  } catch (_) {
    list.innerHTML = `<div class="saved-diet-empty">Saved diets are unavailable right now.</div>`;
  }
}

function applyDietQuantity(mealIndex, itemIndex, inputValue) {
  const meal = activeDietPlan?.[mealIndex];
  const item = meal?.items?.[itemIndex];
  const nextQuantity = Number(inputValue);
  if (!item || !Number.isFinite(nextQuantity) || nextQuantity <= 0 || typeof item.baseQuantity !== "number") return false;
  const ratio = nextQuantity / item.quantity;
  item.quantity = round1(nextQuantity);
  item.calories = round0(Number(item.calories || 0) * ratio);
  item.protein = round1(Number(item.protein || 0) * ratio);
  item.carbs = round1(Number(item.carbs || 0) * ratio);
  item.fat = round1(Number(item.fat || 0) * ratio);
  return true;
}

async function handleMealPlanAction(event) {
  const button = event.target.closest("[data-diet-action]");
  if (!button) return;
  const action = button.dataset.dietAction;
  const mealIndex = Number(button.dataset.mealIndex ?? button.closest("[data-meal-index]")?.dataset.mealIndex ?? -1);
  const itemIndex = Number(button.dataset.itemIndex ?? button.closest("[data-item-index]")?.dataset.itemIndex ?? -1);
  const item = activeDietPlan?.[mealIndex]?.items?.[itemIndex];
  const mealKey = activeDietPlan?.[mealIndex]?.key || button.dataset.meal || "";
  const food = item?.food || button.dataset.food || "general";

  if (action === "favorite" || action === "dislike") {
    const ok = await sendDietFeedback(food, mealKey, action);
    if (!ok) return;
    if (action === "dislike") {
      renderMealPlan(activeDietProfile);
    } else {
      renderMealPlan(activeDietProfile, activeDietPlan);
    }
    return;
  }

  if (action === "replace") {
    const replacement = chooseDietAlternative(mealKey, food, activeDietProfile.preference,
      new Set((activeDietPlan?.[mealIndex]?.items || []).map(x => String(x.food).toLowerCase())));
    if (!replacement || !item) return;
    activeDietPlan[mealIndex].items[itemIndex] = replacement;
    renderMealPlan(activeDietProfile, activeDietPlan);
    return;
  }

  if (action === "apply-quantity") {
    const input = $(
      `.meal-qty-input[data-meal-index="${mealIndex}"][data-item-index="${itemIndex}"]`
    );
    if (applyDietQuantity(mealIndex, itemIndex, input?.value)) {
      renderMealPlan(activeDietProfile, activeDietPlan);
    }
    return;
  }

  if (action === "comment") {
    const comment = $("#dietPlanComment")?.value?.trim() || "";
    if (!comment) return;
    const ok = await sendDietFeedback("general", "", "comment", comment);
    if (!ok) return;
    await saveDietMemoryFromInputs(comment);
    const status = $("#dietMemoryStatus");
    if (status) status.textContent = "Memory updated from feedback";
    $("#dietPlanComment").value = "";
    return;
  }

  if (action === "favorite-plan") {
    await saveCurrentDietPlan(true);
    return;
  }

  if (action === "save-plan") {
    await saveCurrentDietPlan(false);
  }
}

function bindMealPlan() {
  $$("#mealView .meal-choice").forEach(btn => {
    btn.addEventListener("click", () => {
      const field = btn.dataset.mealField;
      const group = btn.parentElement;
      group.querySelectorAll(".meal-choice").forEach(x => x.classList.remove("selected"));
      btn.classList.add("selected");
      mealState[field] = btn.dataset.value;
    });
  });

  const form = $("#mealPlanForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const age = Number($("#mealAge").value);
    const weight = Number($("#mealWeight").value);

    if (!Number.isFinite(age) || age < 16 || age > 80) {
      alert("Please enter an age between 16 and 80.");
      return;
    }
    if (!Number.isFinite(weight) || weight < 35 || weight > 200) {
      alert("Please enter a weight between 35 and 200 kg.");
      return;
    }

    const height = Number($("#mealHeight")?.value || 0) || null;
    const sex = $("#mealSex")?.value || "unspecified";
    const activity = Number($("#mealActivity")?.value || 1.55);
    const waist = Number($("#mealWaist")?.value || 0) || null;
    const neck = Number($("#mealNeck")?.value || 0) || null;
    const hip = Number($("#mealHip")?.value || 0) || null;
    const selectedConditions = $$('input[name="dietCondition"]:checked').map(input => input.value);
    const customCondition = ($("#mealDiseases")?.value || "").trim();
    const diseases = [...selectedConditions, customCondition].filter(Boolean).join(", ");
    const healthNotes = ($("#mealHealthNotes")?.value || "").trim();
    const budget = $("#mealBudget")?.value || "flexible";
    const profile = {age, weight, height, sex, activity, waist, neck, hip, diseases, healthNotes, budget,
      goal: mealState.goal, preference: mealState.preference, country: mealState.country};
    // Explicit allergy/restriction text is treated as a hard exclusion input.
    if (healthNotes) {
      const additions = healthNotes.split(/[,;]+/).map(x => x.trim()).filter(Boolean);
      dietMemory.avoid_foods = [...new Set([...(dietMemory.avoid_foods || []), ...additions])];
    }
    await saveDietMemoryFromInputs(healthNotes ? `Health/dietary note: ${healthNotes}` : "");
    renderMealPlan(profile);
  });

  $("#mealPlanResult")?.addEventListener("click", handleMealPlanAction);
  $("#refreshSavedDiets")?.addEventListener("click", loadSavedDiets);
  $("#savedDietList")?.addEventListener("click", async event => {
    const actionButton = event.target.closest("[data-saved-action]");
    const item = event.target.closest("[data-saved-diet-id]");
    if (!actionButton || !item) return;
    const id = Number(item.dataset.savedDietId);
    const saved = savedDietCache.find(x => Number(x.id) === id);
    if (!saved) return;

    if (actionButton.dataset.savedAction === "open") {
      const payload = saved.plan || {};
      if (payload.profile && payload.plan) {
        renderMealPlan(payload.profile, payload.plan);
      }
      return;
    }

    if (actionButton.dataset.savedAction === "delete") {
      if (!window.confirm("Delete this saved diet?")) return;
      const response = await fetch(`/api/diet/saved/${id}`, {
        method: "DELETE", credentials: "same-origin"
      });
      if (response.ok) await loadSavedDiets();
    }
  });

  void loadDietMemory();
  void loadSavedDiets();
}

async function loadExercises() {
  let data = null;
  try {
    const res = await fetch("/api/exercises", { credentials: "same-origin", cache: "no-store" });
    if (res.ok) data = await res.json();
  } catch (error) {
    console.warn("Exercise API unavailable; loading bundled exercise library.", error);
  }
  if (!data || !Array.isArray(data.exercises) || !data.exercises.length) {
    try {
      const localRes = await fetch("exercise_database_300_plus.json", { cache: "no-store" });
      if (localRes.ok) data = await localRes.json();
    } catch (error) {
      console.error("Bundled exercise library could not be loaded.", error);
    }
  }
  // The bundled database is an object keyed by exercise id, while the API
  // returns an array. Normalize both shapes for the Android/offline build.
  const rawExercises = data && data.exercises;
  if (Array.isArray(rawExercises)) {
    exercises = rawExercises;
  } else if (rawExercises && typeof rawExercises === "object") {
    exercises = Object.entries(rawExercises).map(([id, value]) => ({
      id,
      ...(value || {})
    }));
  } else {
    exercises = [];
  }
  exercises = exercises.filter(ex => ex && ex.id && ex.name);
  $("#exerciseCount").textContent = exercises.length;
  const categories = [...new Set(exercises.map(x => x.category).filter(Boolean))].sort();
  $("#categoryFilter").innerHTML = `<option value="">All categories</option>` + categories.map(c => `<option>${escapeHtml(c)}</option>`).join("");
  renderExercises();
  if (!exercises.length) $("#exerciseGrid").innerHTML = '<p class="empty-state">Exercise library could not load. Please restart the app.</p>';
}

function renderExercises() {
  const query =
    ($("#searchInput").value || "")
      .toLowerCase();

  const category =
    $("#categoryFilter").value;

  const filtered = exercises.filter(ex => {
    const text =
      ex.name.toLowerCase() +
      " " +
      (ex.primary_muscles || [])
        .join(" ")
        .toLowerCase();

    return (
      text.includes(query) &&
      (!category || ex.category === category)
    );
  });

  $("#exerciseGrid").innerHTML =
    filtered.map(ex => {
      const status =
        ex.form_check_status || "COMING_SOON";

      const cls =
        status === "READY"
          ? "ready"
          : status === "BASIC"
            ? "basic"
            : "coming";

      const statusText =
        status === "READY"
          ? "AI FORM READY"
          : status === "BASIC"
            ? "BASIC CHECK"
            : "LIBRARY";

      return `
        <article
          class="exercise-card"
          data-id="${escapeHtml(ex.id)}"
        >
          <div class="exercise-top">
            <span class="tiny-label">
              ${escapeHtml(ex.category)}
            </span>
            <span class="${cls} tiny-label">
              ${statusText}
            </span>
          </div>

          <h4>${escapeHtml(ex.name)}</h4>

          <p>
            ${escapeHtml(
              (ex.primary_muscles || [])
                .join(" • ")
            )}
          </p>

          ${(ex.equipment || [])
            .slice(0, 3)
            .map(
              e =>
                `<span class="tag">
                  ${escapeHtml(e)}
                </span>`
            )
            .join("")}
        </article>
      `;
    })
    .join("");

  $$(".exercise-card").forEach(card => {
    card.onclick = () =>
      selectExercise(card.dataset.id);
  });
}

function resetVisualState() {
  resetPoseTargetLock();
  visual.pipes = [];
  visual.targets = [];
  visual.liveLandmarks = [];
  visual.smoothedLandmarks = [];
  visual.landmarkLowConfidenceFrames = [];
  visual.liveLandmarkPrev = [];
  visual.liveLandmarkTime = 0;
  visual.liveSegments = [];
  visual.pipeStatusByKey = new Map();
  visual.score = 0;
  visual.reps = 0;
  acceptedReps = 0;
  lastRawReps = 0;
  visual.status = "yellow";
  visual.message = "";
  visual.lastView = "";
  visual.frameId++;
  drawClearOverlay();
}

async function selectExercise(id) {
  const ex =
    exercises.find(x => x.id === id);

  if (!ex) return;

  currentExercise = ex;
  resetVisualState();
  setPremappedDemo(ex);

  $("#selectedExerciseTitle")
    .textContent = ex.name;

  $("#selectedExerciseMeta")
    .textContent =
      `${ex.category} • ${ex.difficulty} • ` +
      `${(ex.primary_muscles || []).join(", ")} • ` +
      `${ex.form_check_status}`;

  if (ex.form_check_status !== "READY") {
    setCoachStatus(
      "LIBRARY MODE — FORM RULE NOT READY",
      "var(--muted)"
    );
    showView("form");
    return;
  }

  try {
    const response = await fetch(
      "/api/session",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          exercise: ex.id
        })
      }
    );

    if (!response.ok) {
      let detail = "Pose API unavailable";
      try {
        const errorData = await response.json();
        detail = errorData?.error || detail;
      } catch (_) {}
      throw new Error(detail);
    }

    setCoachStatus(
      "AI FORM CHECK READY",
      "var(--accent)"
    );

  } catch (error) {
    setCoachStatus(
      `AI FORM CHECK ERROR — ${error?.message || "request failed"}`,
      "var(--red)"
    );
  }

  showView("form");

  // When the user just finished a live session, returning to another
  // exercise should resume the camera automatically. First-time entry keeps
  // the existing explicit Enable Camera behavior.
  if (resumeCameraAfterSave) {
    resumeCameraAfterSave = false;
    setTimeout(() => {
      if (currentExercise?.id === ex.id && !cameraStream) {
        enableCamera();
      }
    }, 0);
  }
}


async function checkFormEngineHealth() {
  try {
    const response = await fetch("http://127.0.0.1:5050/api/health", {
      method: "GET",
      cache: "no-store"
    });
    if (!response.ok) throw new Error("health");
    return await response.json();
  } catch {
    return null;
  }
}

function setCoachStatus(text, color) {
  const status = $("#coachStatus");

  status.textContent = text;
  status.style.color = color;
}

function ensureOverlay() {
  const wrap = $("#cameraArea");

  if (!wrap) return null;

  let canvas = $("#poseOverlay");

  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "poseOverlay";

    canvas.style.position = "absolute";
    canvas.style.inset = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "3";

    wrap.appendChild(canvas);
  }

  return canvas;
}

function resizeOverlay() {
  const video = $("#cameraVideo");
  const canvas = ensureOverlay();

  if (
    !video ||
    !canvas ||
    !video.videoWidth ||
    !video.videoHeight
  ) {
    return;
  }

  if (
    canvas.width !== video.videoWidth ||
    canvas.height !== video.videoHeight
  ) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }
}

function drawClearOverlay() {
  const canvas = $("#poseOverlay");

  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  ctx.clearRect(
    0,
    0,
    canvas.width,
    canvas.height
  );
}

function pointToCanvas(point, canvas) {
  // The video uses object-fit: cover and CSS scaleX(-1). The canvas must
  // use the exact same crop/scale math; otherwise pipes drift from the body.
  const video = $('#cameraVideo');
  const vw = video?.videoWidth || canvas.width;
  const vh = video?.videoHeight || canvas.height;
  const cw = canvas.width;
  const ch = canvas.height;

  const scale = Math.max(cw / vw, ch / vh);
  const drawW = vw * scale;
  const drawH = vh * scale;
  const offsetX = (cw - drawW) * 0.5;
  const offsetY = (ch - drawH) * 0.5;

  // Mirror exactly once because the preview video is scaleX(-1).
  return {
    x: offsetX + (1 - Number(point.x)) * drawW,
    y: offsetY + Number(point.y) * drawH
  };
}

function smoothNumber(oldValue, newValue, factor) {
  return oldValue + (newValue - oldValue) * factor;
}

function smoothPoint(oldPoint, newPoint, factor) {
  if (!oldPoint) return { x: newPoint.x, y: newPoint.y };

  const dx = newPoint.x - oldPoint.x;
  const dy = newPoint.y - oldPoint.y;
  const distance = Math.hypot(dx, dy);

  // Responsive on fast movement, more stable on small landmark jitter.
  // These values only affect rendering; they do not change pose decisions.
  const adaptive = distance > 0.055
    ? 0.998
    : distance > 0.025
      ? 0.985
      : 0.96;

  const k = Math.max(factor, adaptive);

  return {
    x: smoothNumber(oldPoint.x, newPoint.x, k),
    y: smoothNumber(oldPoint.y, newPoint.y, k)
  };
}

function pipeSegmentDistance(a, b, x, y) {
  const direct =
    Math.hypot(a.x - x.x, a.y - x.y) +
    Math.hypot(b.x - y.x, b.y - y.y);

  const reverse =
    Math.hypot(a.x - y.x, a.y - y.y) +
    Math.hypot(b.x - x.x, b.y - x.y);

  return Math.min(direct, reverse);
}

function smoothPipes(newPipes) {
  // Match segments by their geometry, never by array index. If a low-
  // confidence joint disappears, the remaining pipe order can change.
  const factor = 0.78;
  const oldPipes = visual.pipes || [];
  const used = new Set();
  const result = [];

  for (const next of newPipes) {
    let bestIndex = -1;
    let bestDistance = Infinity;

    for (let i = 0; i < oldPipes.length; i++) {
      if (used.has(i)) continue;
      const old = oldPipes[i];
      const d = pipeSegmentDistance(old.a, old.b, next.a, next.b);
      if (d < bestDistance) {
        bestDistance = d;
        bestIndex = i;
      }
    }

    const MAX_MATCH_DISTANCE = 0.24;
    const old = bestIndex >= 0 && bestDistance <= MAX_MATCH_DISTANCE
      ? oldPipes[bestIndex]
      : null;

    if (bestIndex >= 0 && old) used.add(bestIndex);

    const normalizedStatus = String(
      next?.status ?? "green"
    ).trim().toLowerCase();

    result.push({
      a: smoothPoint(old?.a, next.a, factor),
      b: smoothPoint(old?.b, next.b, factor),
      status: ["green", "yellow", "red"].includes(normalizedStatus)
        ? normalizedStatus
        : "green"
    });
  }

  visual.pipes = result;
}

function smoothTargets(newTargets) {
  // Yellow target should follow corrections quickly.
  const factor = 0.80;

  if (!visual.targets.length) {
    visual.targets =
      newTargets.map(target => ({
        actual: {...target.actual},
        desired: {...target.desired},
        label: target.label
      }));

    return;
  }

  visual.targets =
    newTargets.map((next, i) => {
      const old = visual.targets[i];

      if (!old) {
        return {
          actual: {...next.actual},
          desired: {...next.desired},
          label: next.label
        };
      }

      return {
        actual: smoothPoint(
          old.actual,
          next.actual,
          factor
        ),
        desired: smoothPoint(
          old.desired,
          next.desired,
          factor
        ),
        label: next.label
      };
    });
}


function applyRedPipeFallback(data) {
  if (String(data?.status || "").toLowerCase() !== "red") {
    return;
  }

  if (!Array.isArray(visual.pipes) || !visual.pipes.length) {
    return;
  }

  const msg = String(data?.message || "").toUpperCase();
  const targets = Array.isArray(data?.targets)
    ? data.targets
    : [];

  const targetLabels = targets
    .map(target => String(target?.[2] ?? target?.label ?? "").toUpperCase());

  const hasAnyRed = visual.pipes.some(
    pipe => String(pipe?.status || "").toLowerCase() === "red"
  );

  // Never overwrite a pipe color when the API already supplied an explicit
  // red pipe. This fallback only repairs missing red visualization.
  if (hasAnyRed) return;

  const exercise = String(
    data?.exercise || currentExercise?.id || ""
  ).toLowerCase();

  const isBothArmFailure =
    msg.includes("BOTH ARMS") ||
    msg.includes("RAISE BOTH ARMS") ||
    msg.includes("PRESS BOTH ARMS") ||
    msg.includes("BOTH SIDES EVEN") ||
    targetLabels.some(label =>
      label.includes("LEFT ELBOW") && targetLabels.some(
        other => other.includes("RIGHT ELBOW")
      )
    );

  const isLegFailure =
    msg.includes("BOTH LEGS") ||
    msg.includes("KNEE ALIGN") ||
    msg.includes("KEEP BOTH KNEES") ||
    targetLabels.some(label =>
      label.includes("LEFT KNEE") && targetLabels.some(
        other => other.includes("RIGHT KNEE")
      )
    );

  if (
    isBothArmFailure &&
    [
      "bicep_curls",
      "hammer_curl",
      "shoulder_press",
      "lateral_shoulder_raises",
      "front_raise",
      "tricep_extension",
      "bench_press",
      "incline_dumbbell_press",
      "decline_bench_press",
      "incline_bench_press",
      "dumbbell_bench_press",
      "close_grip_bench_press",
      "chest_press_machine",
      "chest_fly",
      "cable_crossover",
      "low_cable_crossover"
    ].includes(exercise)
  ) {
    visual.pipes = visual.pipes.map(pipe => ({
      ...pipe,
      status: "red"
    }));
  }

  if (
    isLegFailure &&
    ["squat", "lunges", "reverse_lunge", "step_up", "calf_raise"].includes(
      exercise
    )
  ) {
    visual.pipes = visual.pipes.map(pipe => ({
      ...pipe,
      status: "red"
    }));
  }
}

function drawPoseResult(data) {
  const canvas = ensureOverlay();

  if (!canvas) return;

  resizeOverlay();

  // API responses update coaching/status; current pipe GEOMETRY stays on
  // the newest browser pose so network latency cannot pull the overlay back.
  updatePipeStatusMap(data.pipes || [], visual.liveLandmarks);
  smoothTargets(data.targets || []);
  applyRedPipeFallback(data);

  visual.score = data.score ?? visual.score;

  const rawReps = Number(data.reps ?? lastRawReps);
  const currentStatus = data.status || visual.status || "yellow";

  // Backend RepCounter already rejects RED cycles. GREEN and YELLOW
  // completed cycles are both valid repetitions for the display.
  if (rawReps > lastRawReps) {
    acceptedReps += (rawReps - lastRawReps);
  }

  lastRawReps = Math.max(lastRawReps, rawReps);
  visual.reps = acceptedReps;
  visual.status = currentStatus;
  visual.message = data.message || "";
  visual.lastView = data.view || visual.lastView || "";

  // IMPORTANT:
  // Rendering happens continuously with requestAnimationFrame,
  // while API frames arrive more slowly.
  // This makes the pipes visually smooth instead of jumping.
}

function renderSmoothOverlay() {
  const canvas = ensureOverlay();

  if (!canvas) {
    requestAnimationFrame(renderSmoothOverlay);
    return;
  }

  resizeOverlay();
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // ----------------------------------------------------------
  // PROFESSIONAL FORM PIPES — VISUAL ONLY
  // Same visual endpoints, same status logic, same data.
  // Only the canvas styling is refined here.
  // ----------------------------------------------------------
  const joints = [];

  const styleFor = (status) => {
    if (status === "green") {
      return {
        core: "#2AF58B",
        highlight: "#B9FFD8",
        glow: "rgba(42,245,139,0.38)"
      };
    }
    if (status === "yellow") {
      return {
        core: "#FFD86A",
        highlight: "#FFF1B0",
        glow: "rgba(255,216,106,0.34)"
      };
    }
    return {
      core: "#FF536A",
      highlight: "#FFC2CB",
      glow: "rgba(255,83,106,0.34)"
    };
  };

  for (const pipe of visual.pipes) {
    const a = pointToCanvas(pipe.a, canvas);
    const b = pointToCanvas(pipe.b, canvas);
    const style = styleFor(pipe.status);

    joints.push({ p: a, style }, { p: b, style });

    // Soft outer glow — polished, but intentionally subtle.
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = style.glow;
    ctx.lineWidth = 10;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.shadowBlur = 8;
    ctx.shadowColor = style.glow;
    ctx.stroke();
    ctx.restore();

    // Dark separation ring makes the pipe read clearly on any clothing/background.
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = "rgba(2, 10, 14, 0.86)";
    ctx.lineWidth = 12;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
    ctx.restore();

    // Main pipe.
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = style.core;
    ctx.lineWidth = 7;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
    ctx.restore();

    // Small highlight line gives a cleaner "designed" look without changing geometry.
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = style.highlight;
    ctx.lineWidth = 1.6;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.globalAlpha = 0.72;
    ctx.stroke();
    ctx.restore();
  }

  // ----------------------------------------------------------
  // JOINTS — CONSISTENT PRO NODE DESIGN
  // ----------------------------------------------------------
  const seen = new Set();

  for (const joint of joints) {
    const key =
      `${Math.round(joint.p.x / 3)}:${Math.round(joint.p.y / 3)}:${joint.style.core}`;

    if (seen.has(key)) continue;
    seen.add(key);

    // Outer dark halo
    ctx.beginPath();
    ctx.arc(joint.p.x, joint.p.y, 8.5, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(2,10,14,0.88)";
    ctx.fill();

    // Status-colored node
    ctx.beginPath();
    ctx.arc(joint.p.x, joint.p.y, 5.5, 0, Math.PI * 2);
    ctx.fillStyle = joint.style.core;
    ctx.shadowBlur = 6;
    ctx.shadowColor = joint.style.glow;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Tiny center highlight
    ctx.beginPath();
    ctx.arc(joint.p.x - 1.2, joint.p.y - 1.2, 1.25, 0, Math.PI * 2);
    ctx.fillStyle = joint.style.highlight;
    ctx.globalAlpha = 0.9;
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // ----------------------------------------------------------
  // YELLOW DOTTED CORRECTION GUIDE — VISUAL ONLY
  // ----------------------------------------------------------
  for (const target of visual.targets) {
    const actual = pointToCanvas(target.actual, canvas);
    const desired = pointToCanvas(target.desired, canvas);

    // Soft yellow route glow
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([7, 8]);
    ctx.moveTo(actual.x, actual.y);
    ctx.lineTo(desired.x, desired.y);
    ctx.strokeStyle = "rgba(255,216,106,0.28)";
    ctx.lineWidth = 6;
    ctx.lineCap = "round";
    ctx.shadowBlur = 6;
    ctx.shadowColor = "rgba(255,216,106,0.32)";
    ctx.stroke();
    ctx.restore();

    // Main dotted guide
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([7, 8]);
    ctx.moveTo(actual.x, actual.y);
    ctx.lineTo(desired.x, desired.y);
    ctx.strokeStyle = "#FFD86A";
    ctx.lineWidth = 2.2;
    ctx.lineCap = "round";
    ctx.stroke();
    ctx.restore();

    // Target ring + center
    ctx.beginPath();
    ctx.arc(desired.x, desired.y, 8.5, 0, Math.PI * 2);
    ctx.strokeStyle = "#FFF1B0";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(desired.x, desired.y, 4.8, 0, Math.PI * 2);
    ctx.fillStyle = "#FFD86A";
    ctx.shadowBlur = 8;
    ctx.shadowColor = "rgba(255,216,106,0.42)";
    ctx.fill();
    ctx.shadowBlur = 0;

    if (target.label) {
      // Label only — no logic change.
      ctx.font = "700 13px Inter, system-ui, sans-serif";
      ctx.fillStyle = "#FFF1B0";
      ctx.shadowBlur = 0;
      ctx.fillText(target.label, desired.x + 13, desired.y - 10);
    }
  }

  requestAnimationFrame(renderSmoothOverlay);
}
function updateFormUI(data) {
  const statusText =
    data.status === "green" ? "✓ CORRECT FORM" :
    data.status === "red" ? "✕ FIX YOUR FORM" :
    "→ ADJUST POSITION";

  const statusColor =
    data.status === "green" ? "var(--accent)" :
    data.status === "red" ? "var(--red)" :
    "var(--yellow)";

  setCoachStatus(
    `${statusText} • ${data.score}% • REPS ${data.reps}`,
    statusColor
  );

  const title = $("#formModeName");
  if (title) title.textContent =
    (data.exercise_name || data.exercise || currentExercise?.name || "READY").toUpperCase();

  const meta = $("#selectedExerciseMeta");
  if (meta) {
    meta.textContent =
      `${data.message || "Follow your form guide"} • View: ${data.view || "SIDE"} • Score: ${data.score ?? 0}% • Reps: ${data.reps ?? 0}`;
  }

  const score = $("#metricScore");
  if (score) score.textContent = Number(data.score ?? 0);

  const scoreLabel = $("#scoreLabel");
  if (scoreLabel) {
    scoreLabel.textContent =
      data.status === "green" ? "GOOD FORM" :
      data.status === "red" ? "NEEDS IMPROVEMENT" : "CHECK POSITION";
    scoreLabel.style.color = statusColor;
  }

  const angles = data.angles || {};
  const knee = angles.knee ?? angles.left_knee ?? angles.right_knee ?? angles.knee_angle;
  const back = angles.back ?? angles.back_angle;
  const elbow = angles.elbow ?? angles.left_elbow ?? angles.right_elbow;

  const kneeEl = $("#metricKnee");
  if (kneeEl) kneeEl.textContent = knee != null ? `${Number(knee).toFixed(1)}°` : "—";
  const backEl = $("#metricBack");
  if (backEl) backEl.textContent = back != null ? `${Number(back).toFixed(1)}°` : "—";

  const kneeState = $("#kneeState");
  if (kneeState) kneeState.textContent = knee != null ? (data.status === "red" ? "CHECK" : "GOOD") : "CHECK";
  const backState = $("#backState");
  if (backState) backState.textContent = back != null ? (data.status === "red" ? "CHECK" : "GOOD") : "CHECK";

  const reps = $("#liveReps");
  if (reps) reps.textContent = Number(data.reps ?? 0);

  const bottom = $("#bottomStatus");
  if (bottom) bottom.textContent =
    data.status === "green" ? "RUNNING • GOOD FORM" :
    data.status === "red" ? "RUNNING • CORRECT FORM" : "RUNNING • CHECK POSITION";
  if (bottom) bottom.style.color = statusColor;

  const guide = $("#guideText");
  if (guide) guide.textContent =
    data.status === "green"
      ? "Correct position. Keep this alignment and complete the movement."
      : (data.message ? `${data.message}. Follow the yellow dotted guide.` : "Follow the yellow dotted guide.");

  const tip = $("#tipText");
  if (tip) {
    const cues = currentExercise?.coaching || [];
    tip.textContent = data.status === "green"
      ? (cues[0] || "Good form. Keep the movement controlled.")
      : (data.message || cues[0] || "Follow the yellow dotted correction guide.");
  }

  const feedback = $("#feedbackList");
  if (feedback && currentExercise) {
    const cues = currentExercise.coaching || [];
    const dynamic = [data.message, ...cues].filter(Boolean).slice(0, 4);
    feedback.innerHTML = dynamic.map((cue, i) =>
      `<div class="feedback-row"><span style="background:${i === 0 && data.status === "red" ? "var(--red)" : "var(--accent)"}"></span><b>${escapeHtml(cue)}</b></div>`
    ).join("");
  }

  const analysis = $("#analysisValue");
  if (analysis) analysis.textContent = data.inference_ms != null ? `${Number(data.inference_ms).toFixed(0)}ms` : "LIVE";
  const meter = $("#analysisMeter");
  if (meter && data.inference_ms != null) {
    const pct = Math.max(25, Math.min(100, 100 - Number(data.inference_ms) * 1.5));
    meter.style.width = `${pct}%`;
  }
}


async function loadBrowserMediaPipe() {
  if (window.Pose) return true;

  return new Promise((resolve) => {
    const existing = document.querySelector('script[data-formfit-pose="1"]');
    if (existing) {
      const wait = setInterval(() => {
        if (window.Pose) {
          clearInterval(wait);
          resolve(true);
        }
      }, 50);
      setTimeout(() => {
        clearInterval(wait);
        resolve(!!window.Pose);
      }, 10000);
      return;
    }

    const script = document.createElement('script');
    script.dataset.formfitPose = '1';
    script.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js';
    script.onload = () => resolve(!!window.Pose);
    script.onerror = () => resolve(false);
    document.head.appendChild(script);
  });
}

async function setupBrowserPose() {
  if (browserPoseReady && browserPose) return true;

  const loaded = await loadBrowserMediaPipe();
  if (!loaded) return false;

  browserPose = new window.Pose({
    locateFile: (file) =>
      `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
  });

  browserPose.setOptions({
    modelComplexity: 0,
    smoothLandmarks: true,
    enableSegmentation: false,
    minDetectionConfidence: 0.55,
    minTrackingConfidence: 0.55
  });

  browserPose.onResults((results) => {
    if (!results.poseLandmarks || results.poseLandmarks.length < 33) {
      visual.liveLandmarks = [];
      visual.smoothedLandmarks = [];
      visual.landmarkLowConfidenceFrames = [];
      visual.liveLandmarkPrev = [];
      visual.liveSegments = [];
      visual.pipes = [];
      visual.targets = [];
      setCoachStatus('BODY NOT DETECTED', 'var(--red)');
      return;
    }

    const video = $('#cameraVideo');
    const width = video?.videoWidth || 1280;
    const height = video?.videoHeight || 720;

    const landmarks = results.poseLandmarks.map((lm) => ({
      x: Number(lm.x),
      y: Number(lm.y),
      z: Number(lm.z || 0),
      visibility: Number(lm.visibility ?? 1),
      presence: Number(lm.presence ?? 1)
    }));

    const targetDecision = acceptPoseTarget(landmarks);
    if (!targetDecision.accepted) {
      visual.liveLandmarks = [];
      visual.liveLandmarkPrev = [];
      visual.liveSegments = [];
      visual.pipes = [];
      visual.targets = [];
      setCoachStatus(targetDecision.reason === 'target-switch' ? 'TARGET LOST — WAITING FOR YOU' : 'BODY NOT CLEAR', 'var(--yellow)');
      return;
    }

    // CRITICAL: update live geometry immediately, even when an API request
    // is still in flight. This keeps the camera/overlay path independent
    // from Render latency.
    updateLivePose(landmarks);

    // Keep only one remote analysis request in flight. Camera frames never
    // wait on the network/API.
    if (!browserPoseBusy) {
      void sendLandmarksToAPI(landmarks, width, height);
    }
  });

  browserPoseReady = true;
  return true;
}


function normalizePoint(point) {
  return {
    x: Number(point?.x ?? 0),
    y: Number(point?.y ?? 0)
  };
}

function nearestLiveLandmark(point, landmarks) {
  let best = -1;
  let bestDistance = Infinity;

  for (let i = 0; i < landmarks.length; i++) {
    const lm = landmarks[i];
    const d = Math.hypot(
      Number(point?.x ?? 0) - Number(lm.x),
      Number(point?.y ?? 0) - Number(lm.y)
    );
    if (d < bestDistance) {
      bestDistance = d;
      best = i;
    }
  }

  return bestDistance <= 0.075 ? best : -1;
}

function segmentKey(a, b) {
  return `${Math.min(a, b)}:${Math.max(a, b)}`;
}

function updatePipeStatusMap(apiPipes, landmarks) {
  if (!Array.isArray(apiPipes) || !apiPipes.length) return;

  const next = new Map(visual.pipeStatusByKey);

  for (const pipe of apiPipes) {
    if (!pipe?.a || !pipe?.b) continue;

    const ia = nearestLiveLandmark(normalizePoint(pipe.a), landmarks);
    const ib = nearestLiveLandmark(normalizePoint(pipe.b), landmarks);

    if (ia < 0 || ib < 0 || ia === ib) continue;

    const status = String(pipe.status ?? "green").trim().toLowerCase();
    if (!["green", "yellow", "red"].includes(status)) continue;

    next.set(segmentKey(ia, ib), status);
  }

  visual.pipeStatusByKey = next;

  // Preserve only statuses for anatomically supported segments.
  const supported = new Set(LIVE_SEGMENTS.map(([a, b]) => segmentKey(a, b)));
  for (const key of next.keys()) {
    if (!supported.has(key)) next.delete(key);
  }
}

// Confidence-aware temporal smoothing for the on-screen skeleton.
// This affects rendering only; raw MediaPipe landmarks still go to the form engine.
function smoothLiveLandmarks(landmarks) {
  const previous = visual.smoothedLandmarks || [];
  const lowFrames = visual.landmarkLowConfidenceFrames || [];
  const next = new Array(landmarks.length);

  for (let i = 0; i < landmarks.length; i++) {
    const lm = landmarks[i];
    const old = previous[i];
    const confidence = Math.min(
      Number(lm.visibility ?? 1),
      Number(lm.presence ?? 1)
    );

    if (!Number.isFinite(lm.x) || !Number.isFinite(lm.y)) {
      next[i] = old || { ...lm, visibility: 0, presence: 0 };
      continue;
    }

    if (!old) {
      next[i] = { ...lm };
      lowFrames[i] = confidence < 0.30 ? 1 : 0;
      continue;
    }

    // Briefly hold a previously reliable joint during occlusion, then let it go.
    if (confidence < 0.22) {
      lowFrames[i] = (lowFrames[i] || 0) + 1;
      if (lowFrames[i] <= 2) {
        next[i] = { ...lm, x: old.x, y: old.y, visibility: confidence, presence: confidence };
        continue;
      }
      next[i] = { ...lm };
      continue;
    }

    lowFrames[i] = confidence < 0.35 ? (lowFrames[i] || 0) + 1 : 0;

    const distance = Math.hypot(lm.x - old.x, lm.y - old.y);
    // Filter small jitter more strongly; reduce smoothing on genuine fast movement.
    let alpha = distance > 0.075 ? 0.78 : distance > 0.035 ? 0.48 : 0.30;
    if (confidence < 0.45) alpha *= 0.72;

    next[i] = {
      ...lm,
      x: old.x + (lm.x - old.x) * alpha,
      y: old.y + (lm.y - old.y) * alpha,
      z: Number.isFinite(lm.z) && Number.isFinite(old.z)
        ? old.z + (lm.z - old.z) * alpha
        : (lm.z || 0)
    };
  }

  visual.smoothedLandmarks = next;
  visual.landmarkLowConfidenceFrames = lowFrames;
  return next;
}

function updateLivePose(landmarks) {
  if (!Array.isArray(landmarks) || landmarks.length < 33) return;

  const now = performance.now();
  visual.liveLandmarkPrev = visual.liveLandmarks;
  landmarks = smoothLiveLandmarks(landmarks);
  visual.liveLandmarks = landmarks;
  visual.liveLandmarkTime = now;

  // Build only the anatomical segments that the current AI response has
  // identified. That preserves the existing visual scope of each exercise.
  if (!visual.liveSegments.length) {
    visual.liveSegments = LIVE_SEGMENTS.map(([a, b]) => ({
      aIndex: a,
      bIndex: b,
      key: segmentKey(a, b),
      status: visual.pipeStatusByKey.get(segmentKey(a, b)) || "green"
    }));
  }

  visual.pipes = visual.liveSegments
    .filter(seg => {
      const a = landmarks[seg.aIndex];
      const b = landmarks[seg.bIndex];
      return (
        a && b &&
        Number(a.visibility ?? 1) >= 0.22 &&
        Number(b.visibility ?? 1) >= 0.22
      );
    })
    .map(seg => ({
      a: { x: Number(landmarks[seg.aIndex].x), y: Number(landmarks[seg.aIndex].y) },
      b: { x: Number(landmarks[seg.bIndex].x), y: Number(landmarks[seg.bIndex].y) },
      status: visual.pipeStatusByKey.get(seg.key) || seg.status || "green",
      key: seg.key
    }));
}

async function sendLandmarksToAPI(landmarks, width, height) {
  if (browserPoseBusy || !currentExercise) return;

  browserPoseBusy = true;
  const serial = ++requestSerial;

  try {
    const response = await fetch(
      '/api/analyze_landmarks',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exercise: currentExercise.id,
          width,
          height,
          landmarks
        }),
        cache: 'no-store'
      }
    );

    if (!response.ok) throw new Error(`API ${response.status}`);

    const data = await response.json();
    if (serial !== requestSerial) return;

    if (data.detected) {
      updatePipeStatusMap(data.pipes || [], landmarks);
      drawPoseResult(data);
      updateFormUI(data);
    } else {
      visual.pipes = [];
      visual.liveLandmarks = [];
      visual.liveSegments = [];
      visual.pipeStatusByKey = new Map();
      visual.targets = [];
      setCoachStatus('BODY NOT DETECTED', 'var(--red)');
    }
  } catch (error) {
    console.error('FORMFIT landmark API:', error);

    const message =
      error?.message === 'Failed to fetch'
        ? 'AI FORM ENGINE OFFLINE — keep formfit_api.py running'
        : `AI FORM CHECK ERROR — ${error?.message || 'request failed'}`;

    setCoachStatus(message, 'var(--red)');
  } finally {
    browserPoseBusy = false;
  }
}

async function processBrowserPose() {
  if (!browserPose || !browserPoseReady || !cameraStream) return;

  const video = $('#cameraVideo');
  if (!video || video.readyState < 2) return;

  try {
    // MediaPipe itself is serialized internally; do not tie camera-frame
    // scheduling to the remote API's browserPoseBusy flag.
    await browserPose.send({ image: video });
  } catch (error) {
    console.debug('Pose frame skipped:', error);
  }
}

function startPoseLoop() {
  stopPoseLoop();

  const video = $('#cameraVideo');
  if (!video) return;

  // Best path: schedule exactly when a new decoded camera frame arrives.
  if ("requestVideoFrameCallback" in video) {
    const onVideoFrame = async () => {
      if (!cameraStream) return;
      await processBrowserPose();
      if (cameraStream) {
        poseTimer = video.requestVideoFrameCallback(onVideoFrame);
      }
    };

    poseTimer = video.requestVideoFrameCallback(onVideoFrame);
    return;
  }

  // Compatibility fallback for browsers without requestVideoFrameCallback.
  let lastVideoTime = -1;
  const tick = async () => {
    if (!cameraStream) return;

    const currentVideo = $('#cameraVideo');
    if (
      currentVideo &&
      currentVideo.readyState >= 2 &&
      currentVideo.currentTime !== lastVideoTime
    ) {
      lastVideoTime = currentVideo.currentTime;
      await processBrowserPose();
    }

    poseTimer = requestAnimationFrame(tick);
  };

  poseTimer = requestAnimationFrame(tick);
}

function stopPoseLoop() {
  const video = $('#cameraVideo');

  if (poseTimer) {
    // requestVideoFrameCallback IDs are canceled with cancelVideoFrameCallback.
    if (video && "cancelVideoFrameCallback" in video) {
      try { video.cancelVideoFrameCallback(poseTimer); } catch (_) {}
    }
    cancelAnimationFrame(poseTimer);
    poseTimer = null;
  }
}


function stopFormSession() {
  // Stop only the current form session. Meal Plan and other UI state stay untouched.
  if (formClockTimer) {
    clearInterval(formClockTimer);
    formClockTimer = null;
  }

  stopPoseLoop();

  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }

  const video = $("#cameraVideo");
  if (video) {
    video.pause();
    video.srcObject = null;
  }

  browserPoseBusy = false;
  requestSerial++;
}

function getFormSessionPayload() {
  const duration = formStartTime
    ? Math.max(0, Math.floor((performance.now() - formStartTime) / 1000))
    : 0;

  return {
    kind: "form_session",
    exercise_id: currentExercise?.id || "",
    exercise_name: currentExercise?.name || "",
    reps: Number(visual.reps || 0),
    score: Number(visual.score || 0),
    duration_seconds: duration,
    calories: Math.max(0, Math.round(duration * 0.08)),
    status: visual.status || "",
    view: visual.lastView || "",
    message: visual.message || "",
    payload: {
      exercise: currentExercise?.name || "",
      goal: state.goal || "",
      score: Number(visual.score || 0),
      reps: Number(visual.reps || 0)
    }
  };
}

async function saveCurrentFormSession() {
  if (!currentExercise) return { ok: false, reason: "no_session" };

  const payload = getFormSessionPayload();

  const response = await fetch("/api/history", {
    method: "POST",
    credentials: "same-origin",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    let detail = "Unable to save session";
    try {
      const data = await response.json();
      detail = data.error || detail;
    } catch (_) {}
    throw new Error(detail);
  }

  return await response.json();
}

async function endAndSaveFormSession() {
  const button = $("#endSessionBtn");
  if (button) {
    button.disabled = true;
    button.textContent = "Saving session…";
  }

  try {
    // Remember whether this was a live camera session so the next selected
    // exercise can resume the camera automatically after a successful save.
    resumeCameraAfterSave = Boolean(cameraStream);

    await saveCurrentFormSession();
    stopFormSession();

    currentExercise = null;
    resetVisualState();

    if (button) {
      button.disabled = false;
      button.textContent = "✓ End & Save Session";
    }

    const status = $("#coachStatus");
    if (status) {
      status.textContent = "SESSION SAVED";
      status.style.color = "var(--accent)";
    }

    showView("history");
    await loadHistory();

  } catch (error) {
    console.error("FORMFIT session save:", error);
    const status = $("#coachStatus");
    if (status) {
      status.textContent = "SAVE FAILED — SESSION STILL ACTIVE";
      status.style.color = "var(--red)";
    }
    if (button) {
      button.disabled = false;
      button.textContent = "✓ End & Save Session";
    }
  }
}

async function loadHistory() {
  const list = $("#historyList");
  const summary = $("#historySummary");
  if (!list) return;

  list.innerHTML = '<div class="day-card"><strong>Loading your history…</strong></div>';

  try {
    const response = await fetch("/api/history?limit=50", {
      credentials: "same-origin",
      cache: "no-store"
    });

    if (!response.ok) throw new Error("History unavailable");

    const data = await response.json();
    const items = Array.isArray(data.history) ? data.history : [];

    if (!items.length) {
      if (summary) summary.innerHTML = "";
      list.innerHTML = '<div class="day-card"><strong>No saved sessions yet.</strong><p>Finish a form-check session to see it here.</p></div>';
      return;
    }

    const sessions = items.filter(x => x.kind === "form_session");
    const totalReps = sessions.reduce((n,x) => n + Number(x.reps || 0), 0);
    const avgScore = sessions.length
      ? Math.round(sessions.reduce((n,x) => n + Number(x.score || 0), 0) / sessions.length)
      : 0;

    if (summary) {
      summary.innerHTML = `
        <div class="history-stat"><span>SESSIONS</span><strong>${sessions.length}</strong></div>
        <div class="history-stat"><span>TOTAL REPS</span><strong>${totalReps}</strong></div>
        <div class="history-stat"><span>AVG SCORE</span><strong>${avgScore}%</strong></div>
      `;
    }

    list.innerHTML = items.map(item => {
      const date = item.created_at
        ? new Date(item.created_at).toLocaleString()
        : "Saved session";
      const title = escapeHtml(item.exercise_name || item.exercise_id || "Workout");
      const kind = item.kind === "workout_plan" ? "WORKOUT PLAN" : "FORM SESSION";
      return `
        <article class="day-card history-session-card">
          <div>
            <span class="eyebrow">${kind}</span>
            <strong>${title}</strong>
            <p>${escapeHtml(date)} • ${Number(item.duration_seconds || 0)} sec • ${Number(item.calories || 0)} kcal</p>
          </div>
          <div class="history-session-metrics">
            <span><b>${Number(item.reps || 0)}</b> reps</span>
            <span><b>${Math.round(Number(item.score || 0))}%</b> score</span>
          </div>
        </article>
      `;
    }).join("");

  } catch (error) {
    console.error("FORMFIT history:", error);
    list.innerHTML = '<div class="day-card"><strong>Could not load history.</strong><p>Please make sure the main FormFit server is running.</p></div>';
  }
}

function startFormClock() {
  if (formClockTimer) clearInterval(formClockTimer);
  formStartTime = performance.now();
  formClockTimer = setInterval(() => {
    const el = $("#timeValue");
    if (!el || !formStartTime) return;
    const sec = Math.floor((performance.now() - formStartTime) / 1000);
    const mm = String(Math.floor(sec / 60)).padStart(2, "0");
    const ss = String(sec % 60).padStart(2, "0");
    el.textContent = `${mm}:${ss}`;
    const cal = $("#caloriesValue");
    if (cal) cal.textContent = Math.max(0, Math.round(sec * 0.08));
  }, 1000);
}

async function enableCamera() {
  try {
    setCoachStatus('STARTING AI CAMERA…', 'var(--yellow)');

    const poseLoaded = await setupBrowserPose();
    if (!poseLoaded) {
      throw new Error('Browser MediaPipe failed to load');
    }

    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
        width: { ideal: 1280 },
        height: { ideal: 720 },
        // Ask for smooth/high FPS, but let the browser/camera choose the
        // supported frame rate. We do not force a fixed FPS.
        frameRate: { ideal: 60 }
      },
      audio: false
    });

    const video = $('#cameraVideo');
    video.srcObject = cameraStream;
    video.style.display = 'block';
    video.style.transform = 'scaleX(-1)';
    await video.play();

    ensureOverlay();
    resizeOverlay();

    $('#cameraArea .camera-icon').style.display = 'none';
    $('#cameraArea h3').style.display = 'none';
    $('#cameraArea p').style.display = 'none';
    $('#cameraBtn').style.display = 'none';

    setCoachStatus('AI FORM CHECK RUNNING', 'var(--accent)');
    startFormClock();
    startPoseLoop();
  } catch (error) {
    console.error(error);
    setCoachStatus('CAMERA / MEDIAPIPE FAILED', 'var(--red)');
    alert('Camera or browser AI could not start. Check camera permission and internet connection.');
  }
}

function bindFormChoices() {
  $$(".choice[data-field='goal']")
    .forEach(btn => {
      btn.onclick = () => {
        state.goal =
          btn.dataset.value;

        $$(".choice[data-field='goal']")
          .forEach(
            b =>
              b.classList.remove(
                "selected"
              )
          );

        btn.classList.add(
          "selected"
        );
      };
    });

  $$("#equipmentChoices .choice")
    .forEach(btn => {
      btn.onclick = () => {
        const value = btn.dataset.value;

        if (state.equipment.includes(value)) {
          state.equipment = state.equipment.filter(x => x !== value);
          btn.classList.remove("selected");
          return;
        }

        state.equipment.push(value);
        btn.classList.add("selected");
      };
    });

  const splitSelect = $("#workoutSplit");
  if (splitSelect) {
    splitSelect.value = state.split;
    splitSelect.addEventListener("change", () => {
      state.split = splitSelect.value;
    });
  }

  $("#recommendForm")
    .addEventListener(
      "submit",
      generatePlan
    );
}

async function loadWorkoutMemory() {
  try {
    const response = await fetch("/api/workout/profile", {
      credentials: "same-origin",
      cache: "no-store"
    });
    if (!response.ok) return;
    const data = await response.json();
    Object.assign(workoutMemory, data.profile || {});
  } catch (_) {}
}

async function loadSavedWorkouts() {
  try {
    const response = await fetch("/api/workout/saved", {
      credentials: "same-origin",
      cache: "no-store"
    });
    if (!response.ok) return;
    const data = await response.json();
    savedWorkoutCache = data.saved || [];
    renderSavedWorkouts();
  } catch (_) {}
}

function workoutIdIsIn(key, exerciseId) {
  return (workoutMemory[key] || []).map(String).some(
    x => x.toLowerCase() === String(exerciseId || "").toLowerCase()
  );
}

function workoutActionButton(exercise, action, label) {
  const id = escapeHtml(exercise.exercise_id || "");
  const active =
    action === "favorite" && workoutIdIsIn("favorite_exercises", exercise.exercise_id)
      ? " active"
      : action === "dislike" && workoutIdIsIn("disliked_exercises", exercise.exercise_id)
        ? " active"
        : "";
  return `<button type="button" class="workout-action-btn${active}" data-workout-action="${action}" data-exercise-id="${id}">${label}</button>`;
}

function workoutClonePlan(plan) {
  return JSON.parse(JSON.stringify(plan || {}));
}

function workoutCandidateForReplacement(exerciseId, dayIndex, itemIndex) {
  if (!activeWorkoutPlan?.days?.length) return null;
  const current = activeWorkoutPlan.days[dayIndex]?.exercises?.[itemIndex];
  if (!current) return null;

  const used = new Set(
    activeWorkoutPlan.days.flatMap(day =>
      (day.exercises || []).map(ex => String(ex.exercise_id || "").toLowerCase())
    )
  );

  const candidates = Object.entries(
    Object.fromEntries(exercises.map(ex => [ex.id, ex]))
  ).map(([id, ex]) => ({ id, ex }));

  const profileEquipment = new Set(
    (activeWorkoutProfile?.equipment || []).map(x => String(x).toLowerCase())
  );

  const targetMuscles = new Set(
    (current.primary_muscles || []).map(x => String(x).toLowerCase())
  );

  candidates.sort((a, b) => {
    const score = item => {
      if (item.id === exerciseId) return -999;
      if (used.has(String(item.id).toLowerCase())) return -30;
      if (workoutIdIsIn("avoid_exercises", item.id)) return -1000;
      if (workoutIdIsIn("disliked_exercises", item.id)) return -250;

      let s = 0;
      const equipment = (item.ex.equipment || []).map(x => String(x).toLowerCase());
      const selectedEquipment = profileEquipment;
      const canon = x => ({
        "dumbbell": "dumbbells",
        "dumbbells": "dumbbells",
        "barbell": "barbell",
        "resistance bands": "resistance band",
        "resistance band": "resistance band",
        "body weight": "bodyweight",
        "bodyweight": "bodyweight"
      }[x] || x);
      const normalizedEquipment = new Set(equipment.map(canon));
      const compatible = normalizedEquipment.size > 0 &&
        [...normalizedEquipment].some(x => selectedEquipment.has(x)) &&
        (normalizedEquipment.has("bodyweight") ? selectedEquipment.has("bodyweight") || normalizedEquipment.size > 1 : true);
      if (compatible) s += 12; else s -= 80;

      const muscles = (item.ex.primary_muscles || []).map(x => String(x).toLowerCase());
      if (muscles.some(x => targetMuscles.has(x))) s += 18;

      if (workoutIdIsIn("favorite_exercises", item.id)) s += 15;
      if (item.ex.form_check_status === "READY") s += 4;
      return s;
    };
    return score(b) - score(a);
  });

  const candidate = candidates.find(x =>
    x.id !== exerciseId &&
    !used.has(String(x.id).toLowerCase()) &&
    !workoutIdIsIn("avoid_exercises", x.id) &&
    !workoutIdIsIn("disliked_exercises", x.id)
  );

  if (!candidate) return null;

  const currentEx = current;
  return {
    order: currentEx.order,
    exercise_id: candidate.id,
    exercise: candidate.ex.name || candidate.id,
    category: candidate.ex.category,
    primary_muscles: candidate.ex.primary_muscles || [],
    sets: currentEx.sets,
    reps: currentEx.reps,
    rest_seconds: currentEx.rest_seconds,
    difficulty: candidate.ex.difficulty,
    equipment: candidate.ex.equipment || [],
    camera_view: candidate.ex.recommended_views || [],
    form_check_status: candidate.ex.form_check_status || "COMING_SOON",
    coaching: candidate.ex.coaching || [],
    score: 0
  };
}

function renderSavedWorkouts() {
  const mount = $("#savedWorkoutList");
  if (!mount) return;

  if (!savedWorkoutCache.length) {
    mount.innerHTML = `<div class="saved-workout-empty">No saved workouts yet. Build a plan and save your favorite.</div>`;
    return;
  }

  mount.innerHTML = savedWorkoutCache.map(item => `
    <div class="saved-workout-item" data-saved-workout-id="${Number(item.id)}">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        <small>${item.is_favorite ? "★ Favorite" : "Saved"} • ${escapeHtml(String(item.plan?.days_per_week || ""))} days/week</small>
      </div>
      <div class="saved-workout-actions">
        <button type="button" class="ghost-btn" data-saved-workout-action="open">Open</button>
        <button type="button" class="ghost-btn danger" data-saved-workout-action="delete">Delete</button>
      </div>
    </div>
  `).join("");
}

function renderWorkoutPlan() {
  const result = $("#planResult");
  if (!result || !activeWorkoutPlan) return;

  result.innerHTML = `
    <div class="workout-memory-banner">
      <div>
        <span class="eyebrow">FORMFIT WORKOUT MEMORY</span>
        <strong>${workoutMemory.favorite_exercises.length || workoutMemory.disliked_exercises.length
          ? "Your preferences are being used"
          : "Ready to learn your preferences"}</strong>
      </div>
      <small>Favorites, dislikes and feedback improve future plans.</small>
    </div>

    ${(activeWorkoutPlan.days || []).map((day, dayIndex) => `
      <div class="day-card">
        <div class="workout-day-head">
          <div>
            <h3>Day ${day.day} — ${escapeHtml(day.name)}</h3>
            <small style="color:var(--muted)">${day.warmup_minutes || 5} min warm-up</small>
          </div>
          <span class="badge">${(day.exercises || []).length} exercises</span>
        </div>

        ${(day.exercises || []).map((ex, itemIndex) => `
          <div class="plan-ex workout-plan-ex" data-plan-exercise="${escapeHtml(ex.exercise_id || "")}">
            <div class="workout-plan-main">
              <div class="workout-order">${ex.order}.</div>
              <div>
                <strong>${escapeHtml(ex.exercise)}</strong>
                <small>${escapeHtml((ex.primary_muscles || []).join(" • "))}</small>
              </div>
            </div>

            <span class="badge">${escapeHtml(ex.form_check_status || "LIBRARY")}</span>

            <div class="workout-prescription">
              <label>Sets <input type="number" min="1" max="8" value="${Number(ex.sets || 1)}" data-workout-field="sets" data-day-index="${dayIndex}" data-item-index="${itemIndex}"></label>
              <label>Reps <input type="text" value="${escapeHtml(ex.reps || "")}" data-workout-field="reps" data-day-index="${dayIndex}" data-item-index="${itemIndex}"></label>
              <label>Rest <input type="number" min="0" max="600" value="${Number(ex.rest_seconds || 0)}" data-workout-field="rest" data-day-index="${dayIndex}" data-item-index="${itemIndex}">s</label>
              <button type="button" class="ghost-btn" data-workout-action="apply-edit" data-day-index="${dayIndex}" data-item-index="${itemIndex}">Apply</button>
            </div>

            <div class="workout-action-row">
              ${workoutActionButton(ex, "favorite", "♥ Favorite")}
              ${workoutActionButton(ex, "dislike", "Not for me")}
              <button type="button" class="workout-action-btn" data-workout-action="replace" data-exercise-id="${escapeHtml(ex.exercise_id || "")}" data-day-index="${dayIndex}" data-item-index="${itemIndex}">↻ Replace</button>
              <button type="button" class="workout-action-btn" data-workout-action="comment" data-exercise-id="${escapeHtml(ex.exercise_id || "")}">💬 Comment</button>
            </div>
          </div>
        `).join("")}
      </div>
    `).join("")}

    <div class="workout-save-card">
      <div>
        <span class="eyebrow">SAVE YOUR TRAINING</span>
        <h3>Keep this plan for later</h3>
        <p>Save the current edited workout to your personal library.</p>
      </div>
      <div class="workout-save-actions">
        <button type="button" class="primary-btn" data-workout-action="save">${activeSavedWorkoutId ? "✓ Save changes" : "♡ Save workout"}</button>
        <button type="button" class="ghost-btn" data-workout-action="favorite-save">★ Save as favorite copy</button>
      </div>
    </div>

    <div class="workout-feedback-box">
      <label for="workoutPlanComment">TEACH FORMFIT — COMMENT ON THIS WORKOUT</label>
      <textarea id="workoutPlanComment" placeholder="e.g. I love push-ups, but I don't like lunges. Keep workouts under 45 minutes."></textarea>
      <div class="workout-feedback-actions">
        <button type="button" class="primary-btn" data-workout-action="comment-plan">Save feedback</button>
      </div>
    </div>

    <div class="saved-workout-section">
      <div class="section-mini-head">
        <div>
          <span class="eyebrow">MY SAVED WORKOUTS</span>
          <h3>Personal training library</h3>
        </div>
        <button type="button" class="ghost-btn" data-workout-action="refresh-saved">Refresh</button>
      </div>
      <div id="savedWorkoutList"></div>
    </div>
  `;

  result.querySelectorAll("[data-plan-exercise]").forEach(item => {
    item.addEventListener("click", async event => {
      if (event.target.closest("button,input")) return;
      const exerciseId = item.dataset.planExercise;
      if (exerciseId && typeof selectExercise === "function") {
        await selectExercise(exerciseId);
      }
    });
  });

  renderSavedWorkouts();
}

async function sendWorkoutFeedback(exerciseId, action, comment = "") {
  try {
    const response = await fetch("/api/workout/feedback", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        exercise_id: exerciseId || "general",
        action,
        comment
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Unable to save workout feedback");
    }
    Object.assign(workoutMemory, data.profile || {});
    return true;
  } catch (error) {
    console.error("FORMFIT workout feedback:", error);
    alert(error.message || "Unable to save workout feedback");
    return false;
  }
}

function applyWorkoutEdit(dayIndex, itemIndex) {
  const day = activeWorkoutPlan?.days?.[dayIndex];
  const item = day?.exercises?.[itemIndex];
  if (!item) return false;

  const setInput = $(`input[data-workout-field="sets"][data-day-index="${dayIndex}"][data-item-index="${itemIndex}"]`);
  const repsInput = $(`input[data-workout-field="reps"][data-day-index="${dayIndex}"][data-item-index="${itemIndex}"]`);
  const restInput = $(`input[data-workout-field="rest"][data-day-index="${dayIndex}"][data-item-index="${itemIndex}"]`);

  const sets = Number(setInput?.value);
  const rest = Number(restInput?.value);
  if (!Number.isFinite(sets) || sets < 1 || sets > 8) {
    alert("Sets must be between 1 and 8.");
    return false;
  }
  if (!Number.isFinite(rest) || rest < 0 || rest > 600) {
    alert("Rest must be between 0 and 600 seconds.");
    return false;
  }

  item.sets = Math.round(sets);
  item.reps = String(repsInput?.value || "").trim().slice(0, 30) || item.reps;
  item.rest_seconds = Math.round(rest);
  return true;
}

async function saveCurrentWorkoutPlan(isFavorite = false) {
  if (!activeWorkoutPlan) return false;

  const defaultName = activeSavedWorkoutId
    ? (savedWorkoutCache.find(x => Number(x.id) === Number(activeSavedWorkoutId))?.name || "My Saved Workout")
    : (isFavorite ? "My Favorite Workout" : "My Saved Workout");

  const name = prompt("Name this workout", defaultName);
  if (!name) return false;

  const method = (!isFavorite && activeSavedWorkoutId) ? "PUT" : "POST";
  const url = method === "PUT"
    ? `/api/workout/saved/${Number(activeSavedWorkoutId)}`
    : "/api/workout/saved";

  try {
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        name,
        plan: activeWorkoutPlan,
        is_favorite: isFavorite
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save workout");

    if (method === "POST") {
      activeSavedWorkoutId = Number(data.id);
    }

    await loadSavedWorkouts();
    renderWorkoutPlan();
    return true;
  } catch (error) {
    console.error("FORMFIT saved workout:", error);
    alert(error.message || "Unable to save workout");
    return false;
  }
}

async function openSavedWorkout(id) {
  const item = savedWorkoutCache.find(x => Number(x.id) === Number(id));
  if (!item?.plan) return;
  activeSavedWorkoutId = Number(item.id);
  activeWorkoutPlan = workoutClonePlan(item.plan);
  activeWorkoutProfile = activeWorkoutPlan.profile || activeWorkoutProfile;
  renderWorkoutPlan();
  $("#recommendView")?.scrollIntoView({behavior: "smooth", block: "start"});
}

async function deleteSavedWorkout(id) {
  if (!confirm("Delete this saved workout?")) return;
  try {
    const response = await fetch(`/api/workout/saved/${Number(id)}`, {
      method: "DELETE",
      credentials: "same-origin"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to delete workout");
    await loadSavedWorkouts();
  } catch (error) {
    alert(error.message || "Unable to delete workout");
  }
}

async function handleWorkoutPlanAction(event) {
  const el = event.target.closest("[data-workout-action]");
  if (!el) return;

  const action = el.dataset.workoutAction;
  const exerciseId = el.dataset.exerciseId || "";
  const dayIndex = Number(el.dataset.dayIndex);
  const itemIndex = Number(el.dataset.itemIndex);

  if (action === "favorite" || action === "dislike") {
    const targetList = action === "favorite" ? "favorite_exercises" : "disliked_exercises";
    const otherList = action === "favorite" ? "disliked_exercises" : "favorite_exercises";
    const already = workoutIdIsIn(targetList, exerciseId);

    if (already) {
      workoutMemory[targetList] = (workoutMemory[targetList] || []).filter(
        x => String(x).toLowerCase() !== String(exerciseId).toLowerCase()
      );
    } else {
      workoutMemory[targetList] = [...(workoutMemory[targetList] || []), exerciseId];
      workoutMemory[otherList] = (workoutMemory[otherList] || []).filter(
        x => String(x).toLowerCase() !== String(exerciseId).toLowerCase()
      );
    }

    await sendWorkoutFeedback(exerciseId, action);
    const profile = {
      favorite_exercises: workoutMemory.favorite_exercises,
      disliked_exercises: workoutMemory.disliked_exercises,
      avoid_exercises: workoutMemory.avoid_exercises,
      notes: workoutMemory.notes
    };
    await fetch("/api/workout/profile", {
      method: "PUT",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(profile)
    });
    renderWorkoutPlan();
    return;
  }

  if (action === "replace") {
    const replacement = workoutCandidateForReplacement(exerciseId, dayIndex, itemIndex);
    if (!replacement) {
      alert("No suitable replacement is available with your current equipment and preferences.");
      return;
    }

    activeWorkoutPlan.days[dayIndex].exercises[itemIndex] = replacement;
    await sendWorkoutFeedback(exerciseId, "replace");
    renderWorkoutPlan();
    return;
  }

  if (action === "apply-edit") {
    if (applyWorkoutEdit(dayIndex, itemIndex)) renderWorkoutPlan();
    return;
  }

  if (action === "comment") {
    const comment = prompt("What should FormFit learn about this exercise?");
    if (!comment?.trim()) return;
    await sendWorkoutFeedback(exerciseId, "comment", comment.trim());
    renderWorkoutPlan();
    return;
  }

  if (action === "comment-plan") {
    const comment = $("#workoutPlanComment")?.value?.trim() || "";
    if (!comment) return;
    const ok = await sendWorkoutFeedback("", "comment", comment);
    if (ok) {
      $("#workoutPlanComment").value = "";
      renderWorkoutPlan();
    }
    return;
  }

  if (action === "save") {
    await saveCurrentWorkoutPlan(false);
    return;
  }

  if (action === "favorite-save") {
    await saveCurrentWorkoutPlan(true);
    return;
  }

  if (action === "refresh-saved") {
    await loadSavedWorkouts();
  }
}

function bindSavedWorkoutActions() {
  const list = $("#savedWorkoutList");
  if (!list || list.dataset.bound === "1") return;
  list.dataset.bound = "1";
  list.addEventListener("click", async event => {
    const button = event.target.closest("[data-saved-workout-action]");
    const item = event.target.closest("[data-saved-workout-id]");
    if (!button || !item) return;

    const id = Number(item.dataset.savedWorkoutId);
    if (button.dataset.savedWorkoutAction === "open") {
      await openSavedWorkout(id);
    } else if (button.dataset.savedWorkoutAction === "delete") {
      await deleteSavedWorkout(id);
    }
  });
}

function buildOfflineWorkoutPlan(profile) {
  const equipment = new Set((profile.equipment || []).map(x => String(x).toLowerCase()));
  const canon = value => ({
    "dumbbell": "dumbbells",
    "dumbbells": "dumbbells",
    "body weight": "bodyweight",
    "resistance bands": "resistance band"
  }[String(value).toLowerCase()] || String(value).toLowerCase());
  const compatible = ex => {
    const items = (ex.equipment || []).map(canon);
    if (!items.length) return true;
    return items.some(item => equipment.has(item));
  };
  const pool = exercises.filter(compatible);
  const usable = pool.length ? pool : exercises;
  const count = Math.max(1, Math.min(Number(profile.exercises_per_day) || 5, 10));
  const days = Math.max(1, Math.min(Number(profile.days_per_week) || 3, 7));
  const chosen = usable.slice(0, count);
  return {
    profile: {...profile, offline: true},
    days_per_week: days,
    days: Array.from({length: days}, (_, index) => ({
      day: index + 1,
      name: ["Full Body", "Upper Body", "Lower Body", "Push", "Pull", "Legs", "Recovery"][index] || "Workout",
      warmup_minutes: 5,
      exercises: chosen.map((ex, itemIndex) => ({
        order: itemIndex + 1,
        exercise_id: ex.id,
        exercise: ex.name,
        category: ex.category || "General",
        primary_muscles: ex.primary_muscles || [],
        sets: 3,
        reps: "10-12",
        rest_seconds: 60,
        difficulty: ex.difficulty || "Beginner",
        equipment: ex.equipment || [],
        camera_view: ex.recommended_views || [],
        form_check_status: ex.form_check_status || "LIBRARY",
        coaching: ex.coaching || [],
        score: 0
      }))
    }))
  };
}

async function generatePlan(event) {
  event.preventDefault();

  const profile = {
    goal: state.goal,
    experience: $("#experience").value,
    days_per_week: Number($("#days").value),
    exercises_per_day: Number($("#perDay").value),
    split: state.split || "auto",
    equipment: state.equipment,
    target_muscles: [],
    country: (() => { try { return localStorage.getItem("formfit_country") || "IN"; } catch (_) { return "IN"; } })()
  };

  const result = $("#planResult");
  if (!state.equipment.length) {
    result.innerHTML = `<div class="day-card"><strong>Select your available equipment first.</strong><p style="color:var(--muted)">Bodyweight is only used when you explicitly select Bodyweight.</p></div>`;
    return;
  }
  result.innerHTML = `
    <div class="day-card">
      <strong>Building your intelligent plan…</strong>
      <p style="color:var(--muted)">Using your goal, equipment and learned preferences.</p>
    </div>`;

  try {
    const res = await fetch("/api/recommend", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(profile)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.error || `Recommendation API returned ${res.status}`);
    }

    activeSavedWorkoutId = null;
    activeWorkoutProfile = {...profile, ...(data.profile || {})};
    activeWorkoutPlan = workoutClonePlan(data);
    renderWorkoutPlan();
  } catch (error) {
    console.warn("Recommendation API unavailable; using offline workout planner.", error);
    const offlinePlan = buildOfflineWorkoutPlan(profile);
    activeSavedWorkoutId = null;
    activeWorkoutProfile = {...profile, offline: true};
    activeWorkoutPlan = workoutClonePlan(offlinePlan);
    renderWorkoutPlan();
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener(
  "DOMContentLoaded",
  async () => {
    const countrySelect = document.querySelector("#authCountry");
    if (countrySelect) { try { countrySelect.value = localStorage.getItem("formfit_country") || ""; } catch (_) {} }
    bindNavigation();
bindInternalBackNavigation();
  bindMealPlan();
  bindWinterArc();
    bindFormChoices();

    const planResult = $("#planResult");
    if (planResult) {
      planResult.addEventListener("click", handleWorkoutPlanAction);
    }

    await loadWorkoutMemory();
    await loadSavedWorkouts();

    $("#searchInput")
      .addEventListener(
        "input",
        renderExercises
      );

    $("#categoryFilter")
      .addEventListener(
        "change",
        renderExercises
      );

    $("#cameraBtn").onclick =
      enableCamera;

    $("#backLibrary").onclick =
      () => showView("library");

    window.addEventListener(
      "resize",
      resizeOverlay
    );

    // Start the independent 60-ish FPS
    // visual renderer once.
    requestAnimationFrame(
      renderSmoothOverlay
    );

    await loadExercises();
  }
);
