
FORMFIT V9 — PERFORMANCE REBUILD

BASE:
This V9 is built from the uploaded current formfit_v2 project.
pose_engine.py is copied unchanged from that project.

KEY PERFORMANCE CHANGE:
OLD:
camera -> JPEG -> Flask -> OpenCV -> MediaPipe -> engine -> JSON -> browser

NEW:
camera -> MediaPipe Pose in browser
      -> 33 lightweight landmarks -> Flask
      -> exact pose_engine.py
      -> score/reps/form status
      -> browser

The browser renders a local skeleton continuously with requestAnimationFrame.
The Python engine runs at a controlled ~18 FPS for authoritative form/reps.
The visual layer does NOT wait for each engine response.

FILES TO REPLACE:
    app.js
    formfit_api.py
    styles.css

DO NOT REPLACE:
    pose_engine.py
    app.py
    recommendation_engine.py
    exercise_database_300_plus.json
    index.html

DEPENDENCY:
The browser loads MediaPipe Pose from:
https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js

No new Python package is required.

RUN:
Terminal 1:
    python formfit_api.py

Terminal 2:
    python app.py

Browser:
    Ctrl + Shift + R

IMPORTANT:
An internet connection is required on first load for the browser pose model.
If the model fails to load, the form checker reports the camera/AI error
instead of silently using the old slow JPEG pipeline.
