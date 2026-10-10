
FORMFIT AI — SECOND SCREEN UI + WORKING FUNCTIONS

This package merges the professional second-screen UI with the V7
browser-pose architecture. Do NOT replace pose_engine.py.

FULL REPLACEMENT / COPY INTO formfit_v2:
    index.html
    styles.css
    app.js
    app.py
    formfit_api.py
    recommendation_engine.py
    exercise_database_300_plus.json
    user_profile_schema.json

ADD:
    requirements_web_pose.txt

DO NOT TOUCH:
    pose_engine.py

Run from:
    D:\AI-Gym-FormFit\formfit_v2

Terminal 1:
    .\venv_train\Scripts\activate
    pip install -r requirements_web_pose.txt
    python formfit_api.py

Terminal 2:
    .\venv_train\Scripts\activate
    python app.py

Open:
    http://127.0.0.1:5000

Functions preserved:
- Dashboard navigation
- AI workout recommendation
- Exercise search/filter
- Exercise selection
- Camera permission
- Browser MediaPipe pose tracking
- Exact Python pose_engine form rules
- Green/red/yellow pipes
- Yellow dotted correction targets
- Score
- Reps
- Angles
- Coaching cues
- Live dashboard cards

Why this is merged:
The visual UI files and the functional V7 backend must be used together.
Replacing only the UI files can leave the frontend and pose API on different
versions. This package keeps them synchronized.

If MediaPipe cannot load in the browser, the Form Checker will explicitly
show a camera/MediaPipe error instead of silently failing.
