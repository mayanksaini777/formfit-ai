FORMFIT AUTH FIX

This update changes only authentication backend behavior:
- SQLite registration uses lastrowid instead of RETURNING.
- Postgres keeps RETURNING id.
- Local registration errors now show the actual backend error to aid debugging.
- Existing password show/hide UI is preserved.
- Existing workout/camera/pose/pipes logic is untouched.

Use the ROOT project:
formfit_v2/

Run from that folder:
python app.py

Then test:
1. Create account with a new email.
2. Logout.
3. Login again with the same email/password.

Do not replace unrelated pose/camera files.
