# OVC CaseFile — PRD

## Problem statement
Offline case-management system for South African NPOs serving Orphans & Vulnerable Children (OVC). Django (DRF, Token auth) + PostgreSQL + React. Role-based (admin, supervisor, case-worker, data-capturer). POPIA-aligned audit logging.

## Architecture
- Backend: Django 5.1 + DRF, PostgreSQL, served by uvicorn ASGI (`server:app`) on :8001. Media on local disk.
- Frontend: React (CRA) + Tailwind + shadcn/ui, Token auth in localStorage (`ovc_token`).
- Print/export: server-rendered Django HTML templates with `@media print` CSS (fully offline; browser Print / Save-as-PDF). Auth via `Authorization: Token` header OR `?token=` query (for new-tab opening).

## Core requirements (static)
- Household / caregiver / member records with confirm-before-save trio (surname, id_number, date_of_birth).
- Case-file checklist mirroring physical DSD file; supervisor sign-off.
- Supporting documents (never OCR'd, stored as uploaded).
- RBAC: case-workers scoped to assigned households; audit log admin-only.

## Implemented (2026-06)
- **DSD Print/Export module (CRITICAL)**: official-layout print views for 16 forms — Case File Checklist, CW05 Intake, CW02 Reporter, CW09 Assessment/Planning/Contracting, Family Care Plan, Educational Progress, CW04B External Referral, CW11 Process Note, COW2 Community Process Note, CW13 Termination, Site Visit, Family Exit, Success Story, C06 Monthly Report, HIV Risk Assessment, and Full Case File. Templates in `core/templates/print/`. Endpoint `GET /api/print/<form>/?household_id=&household_ids=`. DB fields pre-filled; checkboxes/section numbering/signature lines match DSD. Per-household "DSD Forms & Printing" panel + checklist print button in UI. Batch printing via `household_ids`.
- **ProcessNote model (CW 11)**: structured process notes (`/api/process-notes/`), add/list/delete UI on household detail, printable on official CW 11 form.
- **File Completeness Sort**: Dashboard toggle (Recent / Least complete); `GET /api/households/?ordering=completeness`.
- **Bulk Reassign**: `/reassign` page (admin/supervisor) — move a batch of households from one case worker to another; `POST /api/households/bulk_reassign/`.
- **Verification Count Badge**: sidebar badge from `/api/households/verification_count/`.
- **Household Timeline**: activity timeline from audit log; `GET /api/households/<id>/timeline/`.
- Fixed: function-based `@api_view` views failed under ASGI (`.accepted_renderer not set`) → converted to APIView classes. Fixed M2M `assigned_to` filter lookup.

### Enhancements (2026-06, round 2)
- **Code Pickers**: CW06 problem codes (96) & CW10 intervention codes (57) exposed via `/api/choices/`; CW11 Process Note editor uses dropdowns.
- **Print Center** (`/print-center`, admin/supervisor): batch-print any DSD form across all households, a case worker's caseload, or a district (via `?household_ids=`).
- **Structured Assessment (CW09)**: `Assessment` model + `/api/assessments/`; in-app editor at `/households/:id/assessment`; prints pre-filled on the official CW09 form.
- **Checklist Sign-off**: supervisor stamps name/SACSSP/date via `POST /api/households/<id>/sign_checklist/`; printed Case File Checklist shows the stamp; action logged to audit/timeline.

### Enhancements (2026-06, round 3)
- **Plan Rows (CW09)**: assessment editor captures Part 4 plan rows (issue/intervention/due-date/responsibility) stored as `Assessment.plan_rows` JSON; they print in the official CW09 Part 4 table.
- **Organisation letterhead**: singleton `Organisation` (name/address/contact/logo) editable by admin at `/settings/organisation` (`/api/organisation/`); prints as the letterhead on every DSD form (gov + org headers).
- **Sign-off History**: admin/supervisor overview at `/signoffs` (`/api/households/?signed=1`) listing signer/SACSSP/date. (Sign-off fields added to `HouseholdListSerializer`.)
- **Batch Cover Page**: Print Center batch runs (2+ households) prepend a cover sheet listing every included household.

### Enhancements (2026-06, round 4)
- **Timeline Sign-off**: checklist sign-off events appear in each household's activity timeline (audit regex already matches `Household #<id>`).
- **On-screen logo**: AppShell fetches `/api/organisation/` and shows the org logo + name in the sidebar and top bar (falls back to default brand). Logo served relative (`/api/media/...`) so it resolves on the public origin.
- **Assessment versions**: multiple CW09 assessments kept per household; editor has a version selector + "New version"; `?assessment_id=` prints a specific version.
- **Cover signatures**: batch cover page shows "Prepared by" + supervisor signature + date lines.
- Fixes (testing agent + main): `OrganisationSerializer.logo` returns a relative URL (build_absolute_uri produced the internal cluster host); print letterhead logo likewise uses a relative src.

### Enhancements (2026-06, round 5)
- **Version labels**: `Assessment.version_number` stamped server-side (Max+1 per household); version picker shows `v{n} · date · author`.
- **Logo in login**: public `GET /api/branding/` (AllowAny) returns org name+logo; login screen shows them.
- **Timeline filters**: household timeline card has action-type filter chips (all + confirmed/edited/printed/...).
- **Cover totals**: batch cover shows average file completeness + a per-household File % column.

## Backlog / next
- P1: add remaining DSD reference forms (CW06 problem codes, CW10 intervention codes as pickers in Process Note dialog; COW1 Planning, CW12 Evaluation, GRW group-work forms).
- P2: batch "Print Center" page (print one form across a district or a worker's caseload).
- P2: structured storage for Family Care Plan / Assessment (currently print-ready blank templates with header pre-filled).

## Test accounts
admin/admin123, supervisor/supervisor123, caseworker/caseworker123, caseworker2/caseworker123, capturer/capturer123. Seed: `python manage.py seed_data` (60 TEST- households).
