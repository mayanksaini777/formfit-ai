# FORMFIT HOSTING — FIRST DEPLOYMENT

This package is based directly on the provided `formfit_v2 (11).zip`.

Architecture:
- `formfit-web` = Flask website
- `formfit-ai` = live pose/form API
- browser talks to `formfit-web`
- `formfit-web` forwards pose requests to `FORMFIT_POSE_API_URL`

## Render

1. Push this folder to GitHub.
2. In Render, use the included `render.yaml` as a Blueprint.
3. Wait for both services to deploy.
4. Open the `formfit-ai` service and copy its public URL.
5. In `formfit-web` environment variables, set:
   `FORMFIT_POSE_API_URL=https://YOUR-AI-SERVICE.onrender.com`
6. Redeploy `formfit-web`.
7. Open the `formfit-web` URL and test login, exercise selection, camera,
   pipes, form score, reps and history.

Important:
- The local SQLite database is intentionally NOT committed.
- For this first host, login/history data is not yet production-durable.
  A persistent Postgres migration should be the next production-hardening step.
- Do not put API keys or secrets in JavaScript or GitHub.
