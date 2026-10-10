
FORMFIT LIVE CHECKER V3

IMPORTANT:
This version connects the website to the exact uploaded pose_engine.py.

DO NOT replace pose_engine.py.

REPLACE:
    app.js
    formfit_api.py

ADD:
    requirements_web_pose.txt

styles.css:
    the package contains the updated complete file; replace it only if
    you want the overlay styling from this version.

RUN:

Terminal 1
----------
cd D:\AI-Gym-FormFit\formfit_v2
.\venv_app\Scripts\activate
pip install -r requirements_web_pose.txt
python formfit_api.py

Terminal 2
----------
cd D:\AI-Gym-FormFit\formfit_v2
.\venv_app\Scripts\activate
python app.py

Open:
http://127.0.0.1:5000

FLOW:

Exercise Library
    -> choose READY exercise
    -> Form Checker
    -> Enable Camera
    -> Browser sends frames
    -> exact pose_engine.py
    -> analyze_exercise()
    -> apply_stability()
    -> RepCounter
    -> JSON
    -> website overlay

The browser now receives:
- green/red/yellow pipes
- yellow dotted correction targets
- correction labels
- score
- reps
- status
- message
- detected view
- measured angles

The existing desktop pose engine rules are not duplicated.
