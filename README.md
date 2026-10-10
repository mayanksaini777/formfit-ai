
# FORMFIT AI

Professional workout-planning and exercise-library web frontend for the FORMFIT AI project.

## Current features

- Professional responsive dashboard
- AI workout onboarding
- Personalized workout plan API
- 154-exercise library
- Search + category filtering
- Manual exercise selection
- Browser camera preview
- Existing Python pose engine remains separate
- Clear distinction between READY / BASIC / COMING_SOON form checking

## Run locally

```bash
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:

`http://127.0.0.1:5000`

## Important architecture

The browser UI does not pretend to perform the Python MediaPipe form analysis.
The Python pose engine remains the form-analysis core.

Next integration step:
connect the live camera/session to the pose engine and stream its
green/red/yellow state, correction pipes, instructions and reps into
the Form Checker page.
