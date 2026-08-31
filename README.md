# OVC CaseFile (Versions-3)

Offline case management for South African NPOs serving orphans and vulnerable children. This is [ofentsesexwale-hue/Versions-3](https://github.com/ofentsesexwale-hue/Versions-3): Django REST API + React (CRA), DSD print forms, household files, assessments, services, and role-based access.

Colour scheme: iOS-style glass on a warm sand canvas. The app is designed to run **offline on a laptop**.

## One-command local start

Install **Python 3.12+** and **Node.js 20+** once (with internet). After that:

```bash
./start-local.sh          # macOS / Linux
start-local.bat          # Windows
```

Open http://127.0.0.1:43141 — API is on 8001, the UI proxies `/api`.

Backup the database and uploaded files:

```bash
cd backend && .venv/bin/python manage.py backup
```

## What the system already does

Households, caregivers, children, checklist, documents, CW09 assessments, CW11 process notes (with CW06/CW10 codes), services, DSD print pack, roles, audit log, reassignment, print centre.

## What is still missing for a live NPO

These are product gaps, not installers:

1. **Child health / HIVSTAT** — HIV risk print form exists; status, ART, and viral load are not stored per child.
2. **Family Care Plan as data** — you can print a blank-ish plan; needs and actions are not saved and reprinted filled.
3. **Case status** — no open / graduated / transferred / lost-to-follow-up on the household.
4. **Education and grants** — school, grade, CSG/FCG/CDG are not first-class fields.
5. **Consent as a record** — on the checklist only, not a signed consent object with date.
6. **More DSD forms** — COW1 planning, CW12 evaluation, GRW group work, Form 22 protection incidents.
7. **Office hardening** — change `admin123`, set a real `DJANGO_SECRET_KEY`, restrict `ALLOWED_HOSTS`, encrypt backups, POPIA file-access policy.
8. **True field offline** — this is a local server, not a tablet app that works with zero LAN. Workers need the laptop (or a LAN) running.

Do not install PostgreSQL unless several staff will use it at once. SQLite is the right default for a single office PC.

## Run locally

You need **Node.js 20+**, **npm**, and **Python 3.11+**. PostgreSQL is optional.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-runtime.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver 127.0.0.1:8001
```

SQLite is used by default (`USE_SQLITE=true`). For PostgreSQL, set `USE_SQLITE=false` and the `POSTGRES_*` variables.

### Frontend

```bash
cd frontend
yarn install
cp .env.example .env
yarn start
```

If you use npm: `npm install --legacy-peer-deps`. The UI runs at [http://127.0.0.1:43141](http://127.0.0.1:43141) and talks to the API at `http://127.0.0.1:8001`.

## Demo logins

| User | Password | Role |
| --- | --- | --- |
| admin | admin123 | admin |
| supervisor | supervisor123 | supervisor |
| caseworker | caseworker123 | case worker |
| capturer | capturer123 | data capturer |

All seeded households are prefixed `TEST` and are fictional.
