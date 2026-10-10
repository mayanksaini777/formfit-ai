FORMFIT — SMART DIET INTELLIGENCE UPDATE v2

Base: user supplied formfit_v2 (20).zip.

Changed only:
- app.py: persistent per-user diet memory, feedback learning, saved/favorite diet CRUD, SQLite/PostgreSQL schema.
- app.js: personalized plan ranking/replacements, favorites/dislikes, manual quantity editing, comments, saved diet library.
- index.html: Food DNA + saved diet controls.
- styles.css: isolated Meal Plan styles.

Protected/untouched: camera, MediaPipe, pipes, reps, form-check logic, exercise selection/library, auth routes, workout history routes, recommendation_engine, formfit_api, pose_engine.

Validation:
- Python syntax PASS.
- JavaScript syntax PASS (node --check).
- No duplicate static HTML IDs.
- Full archive integrity PASS (zip test).

Comment learning is independent per food so mixed feedback such as "I love paneer but I don't like oats" can learn both preferences.
