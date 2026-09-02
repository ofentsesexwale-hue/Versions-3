# OVC CaseFile

Offline case management for South African NPOs serving orphans and vulnerable children. Django REST API + React, household files, DSD print forms, and role-based office logins.

The UI is iOS-style glass on a warm sand canvas. After Python and Node are installed, the office PC can run **without internet**.

## Desktop app (double-click, not a browser)

The office file opens in its **own window** named OVC CaseFile — no Chrome/Edge/Firefox window, no address bar, no browser icon on the taskbar.

**Windows (office PC):** download the new `OVC-CaseFile.exe` (Python and the CaseFile engine are inside it). Put it in `C:\Users\sebue\ovc-case-manager` and double-click it.

If an older `.exe` still asks for Python, open **PowerShell** and paste:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\Users\sebue\ovc-case-manager
.\install-python-and-engine.ps1
```

Or double-click `install-python-and-engine.bat` once (needs internet that first time).

**Linux / this PC:** double-click `start-desktop.sh`, or the AppImage in `desktop/release/` after packing. Put a shortcut on the desktop with `./desktop/install-desktop-shortcut.sh`.

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
| OrphanCoordinator | Khaya-File-7nQ2 | Administrator |

This login is the live office **Administrator** (system builder). Staff accounts cannot demote or deactivate it. From **Staff accounts** this person can add users with a name, title, and login — CYCW, Auxiliary, Caregiver, Supervisor, Data capturer — each with its own permissions. Household caregiver logins can also be set on the caregiver form. Change this password after first sign-in. Dummy TEST- files never appear for this login.

**Training classroom / demo** (fictional TEST- households only — for practice):

All demo classroom logins use the same password: `Practice-File-4kL9`

| User | Password | Title |
| --- | --- | --- |
| demo.admin | Practice-File-4kL9 | Administrator (training) |
| demo.supervisor | Practice-File-4kL9 | Supervisor (QA) |
| demo.cycw | Practice-File-4kL9 | CYCW |
| demo.aux | Practice-File-4kL9 | Auxiliary |
| demo.capturer | Practice-File-4kL9 | Data capturer |

These logins never see live office files. Live office (`OrphanCoordinator`) never sees TEST files.

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
- New household: photograph each sheet you have (C01 can be missing). RapidOCR (`rapidocr-onnxruntime`) reads names on this PC; Tesseract still reads ID digits. An older `.venv` or `.exe` without RapidOCR will say it is not installed — run `start-local` / `install-python-and-engine.bat`, or `pip install rapidocr-onnxruntime onnxruntime` in the same Python that runs Django. Junk OCR is left blank. Check surname / ID / date of birth, then save.
- Scan Intake on an existing file: same photo → read text → confirm path
- Official C01 / CW 05 canvas: type on the real sheet, print that same sheet, scan into the same boxes
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
