# Print template inventory

**Official originals are the Word / `.doc` files** in [`dsd-source/`](dsd-source/).
The full field inventory is [`WORD_TEMPLATES.md`](WORD_TEMPLATES.md).

`NPO_case_management_file.pdf` is a **guide** for how a household file is
assembled. Do **not** write, print, or scan by overlaying that PDF.

**Phase 1 (C01–C03 + CW 05 + FCP + HIV pack print):** filling Official Word
templates and downloading those `.docx` files.

**Phase 2 (C01–C03 + CW 05 + FCP + HIV pack scan blanks):** blank PNGs and
atlas boxes are measured on those Word renders
(`ATLAS_VERSION` `word-c01-c02-c03-cw05-fcp-hiv-v2.4`).
C03 uses **page 1 only**. CW 05 Word exports **4 pages**. Family Care Plan is
**2 landscape** pages. HIV pack sheets are split into their print keys
(`hiv_risk`, `consent`, `client_referral`, `hivstat`).
Other forms still use NPO PDF-derived blanks until their Word phases land.

## Atlas forms

| Code | Official Word source | PDF pp. (guide only) | Blank PNG | Verdict |
| --- | --- | --- | --- | --- |
| `c01` | `dsd-source/Official_C01_Template.docx` | 4–5 | `c01_p0.png`, `c01_p1.png` | **Word print + Word blanks** |
| `intake` (CW 05) | `dsd-source/CW_05_Intake_Form_28082019.docx` | 8–10 | `intake_p0.png`–`p3` | **Word print + Word blanks** (4 pages) |
| `c02` | `dsd-source/C02_Adult_Assessment_Form.docx` | 6 | `c02_p0.png` | **Word print + Word blanks**; atlas identity only |
| `c03` | `dsd-source/C03_Child_Beneficiary_Assessment.docx` | 7 | `c03_p0.png` | **Word print + Word page-1 blank**; atlas identity only (`member.N`) |
| `family_care_plan` | `dsd-source/1Family_Care_Plan.docx` | 12–13 | `family_care_plan_p0`–`p1` | **Word print + Word blanks**; header identity |
| `hiv_risk` | `dsd-source/HIV_Risk_Assessment_Form.docx` (from full pack) | — | `hiv_risk_p0`–`p2` | **Word print + Word blanks**; identity header |
| `consent` | `dsd-source/HIV_Consent_Forms.docx` (caregiver + child assent) | — | `consent_p0`–`p1` | **Word print + Word blanks** |
| `client_referral` | `dsd-source/HIV_Client_Referral_Form.docx` | — | `client_referral_p0`–`p1` | **Word print + Word blanks** (not CW 04B) |
| `hivstat` | `dsd-source/HIV_HTS_Tracking_Form.docx` | — | `hivstat_p0.png` | **Word print + Word blank** |
| `cow2_note` | `dsd-source/COW_2_Process_note_04042019.doc` | Word original | `cow2_p0.png`, `cow2_p1.png` | Overlay on official blank; narratives stay attach-only |

## Word originals not yet on the atlas

| Sheet | File |
| --- | --- |
| Educational Progress Record | `Educational_Progress_Record.docx` |
| Monthly household services (C06 / CO6) | `C06_Monthly_Household_Services_Report.docx` |
| Site Visit + Family Exit | `04_Process_Notes.docx` (two templates in one file) |
| Content page | `Content_Page.docx` |
| NPO check list | `NPO_Check_List.docx` |
| Internal / external referral | `CW_4a_*.doc`, `CW_4b_*.doc` |
| Process note / termination | `CW_11_*.doc`, `CW_13_*.doc` |

The master HIV pack `DSD_HIV_Risk_Assessment_FULL_PACK.docx` remains in
`dsd-source/`; print uses the split sheet files above.

## Older HTML print templates (not the official canvas)

These still exist for batch/full-file printing. They are **INVENTED** relative
to the Word originals (org letterhead, Arial cards, collapsed page count).
Statutory fill/print for C01, CW 05, Family Care Plan, and HIV pack sheets
must **not** use them.

| Key | File | Notes |
| --- | --- | --- |
| `intake` (legacy HTML) | `print/intake.html` | Invented 2-page CW 05 |
| `family_care_plan` (legacy) | `print/family_care_plan.html` | Org header; not the landscape Word grid |
| `monthly_report` | `print/monthly_report.html` | Invented C06 portrait with org logo |
| `process_note` | `print/process_note.html` | Approximate CW 11 |
| `reporter` | `print/reporter.html` | Approximate CW 02 |
| `assessment` | `print/assessment.html` | Approximate CW 09 |
| `referral` | `print/referral.html` | Approximate CW 4B (statutory; separate from HIV-pack Client Referral) |
| `termination` | `print/termination.html` | Approximate CW 13 |
| `hiv_risk`, `hivstat`, `consent` (legacy) | matching HTML | Replaced by Word pack sheets for official print |
| `cow1`, `evaluation`, `group_work` | matching HTML | Approximate COW/GRW |
| `cow2_note` (legacy HTML) | `print/cow2_note.html` | Invented |
| `checklist` | `print/checklist.html` | Approximate; Word original is `NPO_Check_List.docx` |
| `educational`, `site_visit`, `exit`, `success_story`, `form22` | matching HTML | Org-branded; Word originals now exist for educational, site visit, and exit |
| `_gov.html` | shared | Adds org logo on CW sheets — **forbidden on statutory official-canvas pages** |

Girl/Boy Index and family contract: no dedicated Word sheet beyond CW 09.
Attach-only until an original is supplied.

## Source pack

The beneficiary **table of contents** is `Content_Page.docx` (and the scanned
`beneficiary-file-contents.png`), transcribed in
[`BENEFICIARY_FILE_CONTENTS.md`](BENEFICIARY_FILE_CONTENTS.md).

All CW 01–14, COW 1–3, CCG C01–C03/C06, Family Care Plan, educational progress,
process notes, check list, content page, and the HIV pack are in
[`dsd-source/`](dsd-source/). Classify + attach until a Word-fill atlas page
exists.

Still only in earlier uploads, not copied into this folder yet: Group Work
Proposal + GRW 02–04, procedure manual, admin-tools training deck, monthly
reporting workbook.
