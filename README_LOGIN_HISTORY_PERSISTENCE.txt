LOGIN + HISTORY PERSISTENCE FIX

Root cause:
Render web-service filesystems are ephemeral by default, so the app's SQLite
database disappears across redeploys/restarts/spin-downs.

Fix:
- Production switches to Render Postgres when DATABASE_URL is present.
- Local development still uses formfit_users.db.
- Existing auth/history routes are preserved.
- render.yaml creates formfit-db and injects its connection string.
- Added migrate_sqlite_to_postgres.py for any local formfit_users.db that still
  contains accounts/history.

Important:
Previously lost Render SQLite data cannot be recovered by this code alone.
If an old account exists only on the vanished Render filesystem, it will have
to be recreated. A local SQLite DB can be migrated with the helper script.

Render Free Postgres currently expires after 30 days. For a permanent production
launch, upgrade the database to a paid instance before expiry.
