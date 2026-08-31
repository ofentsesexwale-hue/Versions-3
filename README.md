# OVC CaseFile

Offline case management for South African NPOs serving orphans and vulnerable children. Django REST API + React, household files, DSD print forms, and role-based office logins.

The UI is iOS-style glass on a warm sand canvas. After Python and Node are installed, the office PC can run **without internet**.

## Desktop app (double-click, not a browser)

The office file opens in its **own window** named OVC CaseFile — no Chrome/Edge/Firefox window, no address bar, no browser icon on the taskbar.

**Windows:** double-click `start-desktop.bat`, or after a Windows build double-click `desktop/release/OVC-CaseFile.exe`.

**Linux / this PC:** double-click `start-desktop.sh`, or the AppImage in `desktop/release/` after packing.

```bash
chmod +x start-desktop.sh
./start-desktop.sh
```

Build installers (Linux AppImage; Windows `.exe` when Wine or a Windows PC is available):

```bash
chmod +x desktop/pack-desktop.sh
./desktop/pack-desktop.sh
```

Office chimes play on sign-in, errors, successful saves, opening a file by ID, and sign-out. Mute them with the speaker button in the header.

The engine still uses the local Python office file on this computer. Nothing is sent to the internet.

## Browser preview (developers)

```bash
./start-local.sh          # macOS / Linux
start-local.bat           # Windows
```

Open http://127.0.0.1:43141 (API on 8001; the UI proxies `/api`).

Backup SQLite and uploaded files from **Organisation** in the app, or:

```bash
cd backend && .venv/bin/python manage.py backup
```

Restore is administrator-only on the Organisation page (zip created by this app). That stays on the office PC.

## Logins

**Live office** (empty caseload — no dummy households):

| User | Password | Role |
| --- | --- | --- |
| npo.admin | Khaya-File-7nQ2 | Administrator |

Change this password after first sign-in. Add real staff under **Staff accounts**. Dummy TEST- files never appear for this login.

**Training classroom** (fictional TEST- households only — for staff practice):

| User | Password | Role |
| --- | --- | --- |
| admin | admin123 | admin |
| supervisor | supervisor123 | supervisor |
| caseworker | caseworker123 | case worker |
| capturer | capturer123 | data capturer |

Open **Training classroom** on the sign-in screen to fill those usernames.

## Software this build needs

Already wired for a local / Cloud Agent run:

- Python 3.12+ with `backend/requirements-runtime.txt` (Django 5.1, DRF, Pillow, python-dotenv, Faker)
- Node 20+ and Yarn 1 for the React (CRA + craco + Tailwind + shadcn/Radix) UI
- SQLite by default (no PostgreSQL unless several staff share a server)

`./start-local.sh` or `start-local.bat` creates the venv, migrates, seeds training files if missing, builds the UI, and serves preview on port 43141.

## Open a file by ID number

On the dashboard or in the header search, type a South African ID (or passport digits). Spaces and dashes are ignored. If that number belongs to one household, the file opens immediately — the same idea as looking someone up in Access. Microsoft Access can still be imported later; this office file is the live source of truth.

If several people share a partial number, you get a list. If nobody matches, you stay on search with an empty result.

## What you can capture

- Households with case status (open, graduated, transferred, lost to follow-up, closed)
- Caregiver and children (confirm surname, ID, date of birth before save)
- School, grade, and grant types (CSG / FCG / CDG and others)
- Child HIVSTAT: status, ART, viral load, last test (need-to-know health data)
- Dated consent (services, information sharing, photo) with caregiver sign-off and child assent
- Work diary: planned home/school visits, overdue follow-ups
- External referrals (SASSA, clinic, school, SAPS) with status until closed
- Local partner directory (typed in on this PC — never looked up online)
- SA ID checksum, date-of-birth/sex from the 13 digits, and a warning if that ID is already on another file
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
