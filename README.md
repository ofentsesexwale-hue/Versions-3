# OVC CaseFile

Offline case management for South African NPOs serving orphans and vulnerable children. Django REST API + React, household files, DSD print forms, and role-based office logins.

The UI is iOS-style glass on a warm sand canvas. After Python and Node are installed, the office PC can run **without internet**.

## Desktop app (double-click, not a browser)

The office file opens in its **own window** named OVC CaseFile — no Chrome/Edge/Firefox window, no address bar, no browser icon on the taskbar.

**Windows (office PC):** put `OVC-CaseFile.exe` in `C:\Users\sebue\OVC-CaseFile` (not `ovc-case-manager` — that is a different app). Double-click the `.exe`.

With Wi-Fi, in File Explorer open the unzipped folder (`Versions-3-main`) and **double-click `DOUBLE-CLICK-TO-INSTALL.bat`**. Do not type `cd` or `py`. That script installs Python 3.12 if missing, RapidOCR, Tesseract, and the VC++ runtime, then writes `install-office-engine.log`. Then start the app from that same folder.

## What to download on the office PC (Wi-Fi is fine)

These stay **on this computer**. Photos are not sent to the cloud.

| Install | Why | GitHub / download |
| --- | --- | --- |
| **Tesseract 64-bit Windows** | Printed 13-digit IDs | [tesseract-ocr/tesseract releases](https://github.com/tesseract-ocr/tesseract/releases/latest) — file `tesseract-ocr-w64-setup-*.exe`. Wiki: [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) |
| **RapidOCR** | Handwritten names | [RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) then `pip install rapidocr-onnxruntime onnxruntime` |
| **ONNX Runtime** | Runs RapidOCR | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) (use pip, not the C++ zip) |
| **Python 3.12** | Runs the office file | [python/cpython](https://github.com/python/cpython) — Windows `.exe` from [python.org 3.12](https://www.python.org/downloads/release/python-31210/) |
| **This office file** | The app | [ofentsesexwale-hue/Versions-3](https://github.com/ofentsesexwale-hue/Versions-3) |
| **iPhone: Most Compatible** | Avoids HEIC | Settings → Camera → Formats (no download) |

Do **not** install extra OCR websites, ChatGPT, Google Lens, or PaddlePaddle GPU packs — they either leave the PC or do not plug into this file.

Optional and **not** needed for daily casework: Node/Yarn (only if you rebuild the UI), Afrikaans Tesseract language data (DSD sheets are English).

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

This login is the live office **Administrator** (system builder). Staff accounts cannot demote or deactivate it. From **Staff accounts** this person can add users with a name, title, and login — E.P.W.P Coordinator, Poverty Alleviator Coordinator, CYCW, Auxiliary, Caregiver, Caregiver (E.P.W.P), Supervisor, Data capturer — each with its own permissions. Household caregiver logins can also be set on the caregiver form. Change this password after first sign-in. Dummy TEST- files never appear for this login.

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

- Python 3.12+ with `backend/requirements-runtime.txt` (Django 5.1, DRF, Pillow, RapidOCR, onnxruntime, pytesseract)
- Tesseract-OCR **program** (not only the pip wrapper) for printed ID digits
- Node 20+ and Yarn 1 only when rebuilding the React UI
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
- New household: photograph each sheet you have (C01 can be missing). Scan Intake aligns photos to the official blanks — C01 uses `Official_C01_Template.docx` pages, other forms still use the NPO PDF. RapidOCR (`rapidocr-onnxruntime`) reads names on this PC; Tesseract still reads ID digits. An older `.venv` or `.exe` without RapidOCR will say it is not installed — run `start-local` / `install-python-and-engine.bat`, or `pip install rapidocr-onnxruntime onnxruntime` in the same Python that runs Django. Junk OCR is left blank. Check surname / ID / date of birth, then save.
- Scan Intake on an existing file: same photo → read text → confirm path
- Official C01: print fills the Word template; Scan Intake reads the same Word blank geometry. CW 05 and other sheets still use the NPO PDF canvas.
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

## Go live (single office PC)

1. Copy `backend/.env.example` → `backend/.env`.
2. Set a new `DJANGO_SECRET_KEY` (long random string). Leave `DJANGO_DEBUG=False`. Set `DJANGO_ALLOWED_HOSTS` for this PC.
3. Optionally set `MEDIA_ROOT` to a dedicated folder on the office drive (leave blank to use `backend/media`).
4. From `backend` with the venv active:

```bash
python manage.py migrate
python manage.py disable_training_users
python manage.py production_check
python manage.py backup
```

`production_check` must show PASS on DEBUG, secret key, training users inactive, writable MEDIA_ROOT, and backup folder. It never deletes SI- households.

Restore from a zip (will not overwrite live files unless forced):

```bash
python manage.py restore path/to/ovc-backup-YYYYMMDD-HHMMSS.zip --force
```

BitLocker disk encryption, Windows auto-lock when idle, and copying backup zips to an external drive are **manual Windows steps** — this app does not turn those on.

### Windows `.exe` and torch (8 GB office PC)

`OVC-CaseFile.exe` runs the **bundled** `office/python` (from `desktop/vendor/python-win`), not `backend\.venv` and not a `%TEMP%` extract.

**Do not** ask staff to `pip install` into `%TEMP%` portable extracts of the `.exe`. Those folders are wiped or corrupted on restart and cause `torchvision\_C.pyd` / “entry point not found” errors. Always rebuild the exe from a matched vendor stack.

Bundled pins (install only torch/torchvision from `https://download.pytorch.org/whl/cpu`):

- `torch==2.14.0+cpu`
- `torchvision==0.29.0+cpu`
- `transformers==4.49.0`
- `tokenizers==0.21.4` (required with transformers 4.49 — 0.23.x breaks TrOCR with `RobertaProcessing … 'cls'`)
- `opencv-python-headless`

Build machine:

```bash
desktop/bundle-windows-python.sh   # or on Windows: desktop\ensure-windows-torch.bat
# verify:
#   python -c "import torch, torchvision; from transformers import TrOCRProcessor; print(torch.__version__, torchvision.__version__, 'TrOCR OK')"
cd desktop && yarn pack:win
```

Model weights stay in `%USERPROFILE%\.cache\huggingface` — they are not packed into the exe.

On the office PC, after replacing the exe:

1. Keep a copy of the old file as `OVC-CaseFile.exe.bak`.
2. Put the new `desktop\release\OVC-CaseFile.exe` (or repo-root copy) in `C:\Users\sebue\OVC-CaseFile\`.
3. Open **New household** — it must not say `No module named torch`, and Scan Intake must not 502 on first TrOCR load.

If packing is too heavy on 8 GB RAM, use the venv launcher instead:

```bat
start-desktop.bat
desktop\use-venv-shortcut.bat
```

That shortcut runs `backend\.venv` (where torch is already installed) and still uses the same Hugging Face cache.
