# Exact FormFit Web Integration

Put `formfit_api.py` and the provided `pose_engine.py` in the same folder.

The API uses the existing engine's:
- analyze_exercise()
- LandmarkSmoother
- DecisionStabilizer
- TargetSmoother
- RepCounter

It therefore keeps the existing exercise rules, side-view logic, green/red
pipes, yellow dotted correction targets, score, and rep counter.

Install:
    pip install -r requirements_web_pose.txt

Run:
    python formfit_api.py

Test:
    http://127.0.0.1:5050/api/health

Then connect the website Form Checker to:
    POST http://127.0.0.1:5050/api/analyze
