FORMFIT — KNOWN-GOOD BASELINE HOST PATCH

Source of truth:
formfit_v2 (11)(1).zip supplied by the user as the pre-hosting working version.

Only hosting glue was added:
- web server reads FORMFIT_POSE_API_URL
- web app proxies /api/session to the existing AI API
- existing /api/analyze_landmarks proxy uses the same configurable URL
- Render PORT/0.0.0.0 binding
- Gunicorn dependencies
- MediaPipe pinned to 0.10.21 for legacy mp.solutions
- Render Blueprint for formfit-web + formfit-ai
- frontend session call is same-origin
- existing logout route is wired to the existing logout button
- browser Back navigation returns to internal views

IMPORTANT:
SQLite auth/history remains intentionally unchanged in this baseline-preserving
patch. This is to restore working behavior first. Persistent Postgres is a
separate step after live functionality is verified.
