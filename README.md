# OVC CaseFile

Offline case management for South African NPOs serving orphans and vulnerable children. Django REST API + React, household files, DSD print forms, and role-based office logins.

The UI is iOS-style glass on a warm sand canvas. After Python and Node are installed, the office PC can run **without internet**.

## Start on the office laptop

```bash
./start-local.sh          # macOS / Linux
start-local.bat           # Windows
```

Open http://127.0.0.1:43141 (API on 8001; the UI proxies `/api`).

Backup SQLite and uploaded files:

```bash
cd backend && .venv/bin/python manage.py backup
```

## Add real staff (not only demo users)

1. Sign in as administrator.
2. Open **Staff accounts**.
3. Create each worker: username, password (8+ characters, not a common password), name, and role (administrator, supervisor, case worker, data capturer).
4. Each person should open **Change password** after first login and replace any shared password.
5. Assign households to case workers from **Edit household**.

Demo accounts (`admin` / `admin123`, and the other seeded users) are optional practice logins. You can deactivate them once real staff exist. Keep at least one active administrator.

Set `DJANGO_SECRET_KEY` in `backend/.env` before going live.

## What you can capture

- Households with case status (open, graduated, transferred, lost to follow-up, closed)
- Caregiver and children (confirm surname, ID, date of birth before save)
- School, grade, and grant types (CSG / FCG / CDG and others)
- Child HIVSTAT: status, ART, viral load, last test (need-to-know health data)
- Dated consent (services, information sharing, photo) with caregiver sign-off and child assent
- Family care plan rows that print filled
- CW 09 assessments, CW 11 process notes, CW 12 evaluations
- COW 1 community plans, GRW group sessions, Form 22 protection incidents
- Services, documents, checklist sign-off, audit log, print pack

## Run without the launcher

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-runtime.txt
python manage.py migrate
python manage.py seed_data   # optional fictional TEST- households
python manage.py runserver 127.0.0.1:8001
```

```bash
cd frontend
yarn install
cp .env.example .env
yarn build
# serve frontend/build via start-local.sh / preview_server.py
```

SQLite is the default (`USE_SQLITE=true`). Use PostgreSQL only if several staff share one server.

Seeded households are prefixed `TEST` and are fictional.
