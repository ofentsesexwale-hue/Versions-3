# OVC CaseFile (Versions-3)

Offline case management for South African NPOs serving orphans and vulnerable children. This is [ofentsesexwale-hue/Versions-3](https://github.com/ofentsesexwale-hue/Versions-3): Django REST API + React (CRA), DSD print forms, household files, assessments, services, and role-based access.

Colour scheme: **yellow, black, and brown**.

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
