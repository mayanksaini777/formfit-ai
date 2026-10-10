import os, sqlite3, sys
import psycopg

src_path = sys.argv[1] if len(sys.argv) > 1 else "formfit_users.db"
url = os.environ.get("DATABASE_URL", "").strip()
if not url:
    raise SystemExit("DATABASE_URL is required.")

src = sqlite3.connect(src_path)
src.row_factory = sqlite3.Row

with psycopg.connect(url) as dst:
    with dst.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS workout_history (
            id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL DEFAULT 'form_session', exercise_id TEXT, exercise_name TEXT,
            reps INTEGER NOT NULL DEFAULT 0, score DOUBLE PRECISION NOT NULL DEFAULT 0,
            duration_seconds INTEGER NOT NULL DEFAULT 0, calories DOUBLE PRECISION NOT NULL DEFAULT 0,
            status TEXT, view TEXT, message TEXT, payload_json TEXT, created_at TEXT NOT NULL)""")

        users=src.execute("SELECT id,email,password_hash,created_at FROM users ORDER BY id").fetchall()
        for row in users:
            cur.execute("""INSERT INTO users(id,email,password_hash,created_at)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT(email) DO UPDATE SET
                           password_hash=EXCLUDED.password_hash,
                           created_at=EXCLUDED.created_at""", tuple(row))

        hist=src.execute("""SELECT id,user_id,kind,exercise_id,exercise_name,reps,score,
                            duration_seconds,calories,status,view,message,payload_json,created_at
                            FROM workout_history ORDER BY id""").fetchall()
        for row in hist:
            cur.execute("""INSERT INTO workout_history(
                           id,user_id,kind,exercise_id,exercise_name,reps,score,
                           duration_seconds,calories,status,view,message,payload_json,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(id) DO NOTHING""", tuple(row))

print(f"Migrated {len(users)} users and {len(hist)} history rows.")
