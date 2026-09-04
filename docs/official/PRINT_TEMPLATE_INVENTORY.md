# Print template inventory

**Official originals are the Word / `.doc` files** in [`dsd-source/`](dsd-source/).
The full field inventory is [`WORD_TEMPLATES.md`](WORD_TEMPLATES.md).

`NPO_case_management_file.pdf` is a **guide** for how a household file is
assembled. Do **not** write, print, or scan by overlaying that PDF.

**Current atlas version:** `word-c01-c02-c03-cw05-fcp-hiv-remaining-v2.5`

## Atlas forms on Official Word (print downloads `.docx`)

| Code | Official Word source | Blank PNG | Notes |
| --- | --- | --- | --- |
| `c01` | `Official_C01_Template.docx` | `c01_p0`–`p1` | Full identity |
| `c02` | `C02_Adult_Assessment_Form.docx` | `c02_p0` | Identity only |
| `c03` | `C03_Child_Beneficiary_Assessment.docx` | `c03_p0` | Page 1 only |
| `intake` | `CW_05_Intake_Form_28082019.docx` | `intake_p0`–`p3` | 4 pages |
| `family_care_plan` | `1Family_Care_Plan.docx` | `family_care_plan_p0`–`p1` | Header identity |
| `hiv_risk` | `HIV_Risk_Assessment_Form.docx` | `hiv_risk_p0`–`p2` | From HIV pack |
| `consent` | `HIV_Consent_Forms.docx` | `consent_p0`–`p1` | Caregiver + child assent |
| `client_referral` | `HIV_Client_Referral_Form.docx` | `client_referral_p0`–`p1` | HIV-pack referral (not CW 4b) |
| `hivstat` | `HIV_HTS_Tracking_Form.docx` | `hivstat_p0` | HTS / beneficiary details |
| `monthly_report` | `C06_Monthly_Household_Services_Report.docx` | `monthly_report_p0` | Landscape |
| `educational` | `Educational_Progress_Record.docx` | `educational_p0` | Landscape |
| `site_visit` | `Site_Visit_Form.docx` | `site_visit_p0` | Split from `04_Process_Notes.docx` |
| `exit` | `Family_Exit_Form.docx` | `exit_p0` | Split from `04_Process_Notes.docx` |
| `checklist` | `NPO_Check_List.docx` | `checklist_p0` | Supervisor checklist |
| `content_page` | `Content_Page.docx` | `content_page_p0` | File index |
| `process_note` | `CW_11_Process_note_28082019.docx` | `process_note_p0`–`p2` | From official `.doc` |
| `termination` | `CW_13_Termination_report_28082019.docx` | `termination_p0` | From official `.doc` |
| `internal_referral` | `CW_4a_Internal_Referral_form_28082019.docx` | `internal_referral_p0`–`p1` | From official `.doc` |
| `referral` | `CW_4b_External_Referral_form_28082019.docx` | `referral_p0`–`p2` | From official `.doc` |

## Still not Official Word print (legacy HTML invents)

These Print Center keys still use invented HTML templates (org letterhead /
collapsed layouts). Official `.doc` originals may exist in `dsd-source/` but
are **not** wired to Word fill yet:

| Key | Official original on disk | Print today |
| --- | --- | --- |
| `reporter` | `CW_02_Reporter_Form_28082019.doc` | HTML invent |
| `assessment` | `CW_09_Assessment_Planning_and_contracting_28082019.doc` | HTML invent |
| `cow1` | `COW_1_Planning_04042019.doc` | HTML invent |
| `evaluation` | `CW_12_Evaluation_28082019.doc` / `COW_3_*.doc` | HTML invent |
| `group_work` | GRW pack (not in `dsd-source/` yet) | HTML invent |
| `form22` | No dedicated Word sheet | HTML invent |
| `success_story` | No dedicated Word sheet | HTML invent |
| `full` | Bundle of sections | HTML invent |

## Official blank that is PDF (not NPO, not Word PNG from this phase)

| Code | Source | Notes |
| --- | --- | --- |
| `cow2_note` | `docs/official/COW_2_Process_note_04042019.pdf` (from COW 2 `.doc`) | Official COW PDF blank + canvas overlay — **not** the NPO case-management PDF |

## NPO case-management PDF

**No atlas blank currently comes from `NPO_case_management_file.pdf`.**

That file remains a **file-order guide only**. Do not overlay it for print or scan.

## Older HTML templates still in the repo

Legacy HTML under `core/templates/print/` remains for batch/`full` printing and
for the not-yet-migrated keys above. Official Word print must **not** use those
HTML invents for forms that already have Word keys in the atlas table.

Girl/Boy Index and family contract: no dedicated Word sheet beyond CW 09.
Attach-only until an original is supplied.

## Source pack notes

- Master HIV pack: `DSD_HIV_Risk_Assessment_FULL_PACK.docx` (split sheets used for print).
- Master process-notes Word: `04_Process_Notes.docx` (Site Visit + Family Exit splits).
- CW 4a / 4b / 11 / 13 keep original `.doc` plus LibreOffice `.docx` companions for fill.
- Still only in earlier uploads / not required for print: Group Work Proposal +
  GRW 02–04, procedure manual, admin-tools deck, monthly reporting workbook,
  CW 01/08/14 spreadsheets, CW 03/06/07/10 reference sheets.
