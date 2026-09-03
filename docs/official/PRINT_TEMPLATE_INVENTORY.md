# Print template inventory

Official wording and geometry come from `NPO_case_management_file.pdf` (38-page NPO case file). Fill, print, and Scan Intake share one atlas and the frozen blank PNGs in `backend/core/official_blanks/`. Those PNGs are rendered from the PDF at scale 2.0 (landscape sheets rotated 90° so the printed face is upright). A standing test re-renders the PDF and checks SHA-256 against `blanks.json`. If that test fails, fill/print and scan have drifted.

## Atlas forms (this pass)

| Code | Official sheet | PDF pp. | Blank PNG | Verdict |
| --- | --- | --- | --- | --- |
| `c01` | C01 Household Details CCG Form v.1.2 | 4–5 | `c01_p0.png`, `c01_p1.png` | **FAITHFUL** — print is the PDF blank + overlay ink, not a redrawn table |
| `intake` (CW 05) | CW 05 Intake Form, DSD header | 8–10 | `intake_p0.png`–`p2` | **FAITHFUL** — same |
| `c02` | C02 ADULT Assessment, landscape | 6 | `c02_p0.png` | **FAITHFUL** blank; structured extract = identity only (ticks have no serializer) |
| `c03` | C03 CHILD Beneficiary Assessment, landscape | 7 | `c03_p0.png` | **FAITHFUL** blank; identity only |
| `cow2_note` | COW 02 Community Work Process Note, DSD header | Word original | `cow2_p0.png`, `cow2_p1.png` | **FAITHFUL** — print is the official blank + overlay (household number, town, assigned worker). Narratives stay attach-only. |

## Older HTML print templates (not the official canvas)

These still exist for batch/full-file printing. They are **INVENTED** relative to the PDF (org letterhead, Arial cards, collapsed page count). Statutory fill/print for C01 and CW 05 must **not** use them.

| Key | File | Notes |
| --- | --- | --- |
| `intake` (legacy HTML) | `print/intake.html` | Invented 2-page CW 05; superseded by official canvas when printing `intake` |
| `family_care_plan` (legacy) | `print/family_care_plan.html` | Org header; not PDF landscape grid |
| `monthly_report` | `print/monthly_report.html` | Invented C06 portrait with org logo |
| `process_note` | `print/process_note.html` | Approximate CW 11 with DSD header + org logo in `_gov.html` |
| `reporter` | `print/reporter.html` | Approximate CW 02 |
| `assessment` | `print/assessment.html` | Approximate CW 09 |
| `referral` | `print/referral.html` | Approximate CW 4B |
| `termination` | `print/termination.html` | Approximate CW 13 |
| `hiv_risk`, `hivstat`, `consent` | matching HTML | Approximate; HIV ticks not stored unless already on the member model |
| `cow1`, `evaluation`, `group_work` | matching HTML | Approximate COW/GRW |
| `cow2_note` (legacy HTML) | `print/cow2_note.html` | Invented; superseded by official canvas when printing `cow2_note` |
| `checklist` | `print/checklist.html` | Approximate NPO checklist |
| `educational`, `site_visit`, `exit`, `success_story`, `form22` | matching HTML | Org-branded / invented — attach-only is enough |
| `_gov.html` | shared | Adds org logo on CW sheets — **forbidden on statutory official-canvas pages** |

Girl/Boy Index and family contract: no atlas. Attach-only.

## Source pack held for later (not yet atlas)

The beneficiary **table of contents** (Yes/No evidence checklist) is `beneficiary-file-contents.png`, transcribed in [`BENEFICIARY_FILE_CONTENTS.md`](BENEFICIARY_FILE_CONTENTS.md).

Official CW 01–14 and COW 1–3 Word/Excel originals are in [`dsd-source/`](dsd-source/). Classify + attach until an atlas page exists.

Still only in earlier uploads, not copied into this folder yet: Group Work Proposal + GRW 02–04, procedure manual, admin-tools training deck, monthly reporting workbook.
