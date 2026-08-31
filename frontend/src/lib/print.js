import { TOKEN_KEY } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// The organisation name/logo used on printed forms now comes from the backend
// Organisation profile; only pass `org` to override it explicitly.
export const ORG_NAME = "Sebueng Itumeleng";

// Per-household DSD forms (official Department of Social Development templates).
export const DSD_FORMS = [
  { key: "full", label: "Full Case File", group: "Case file" },
  { key: "checklist", label: "Case File Checklist", group: "Case file" },
  { key: "intake", label: "CW 05 Intake Form", group: "Intake & assessment" },
  { key: "reporter", label: "CW 02 Reporter Form", group: "Intake & assessment" },
  { key: "assessment", label: "CW 09 Assessment, Planning & Contracting", group: "Intake & assessment" },
  { key: "family_care_plan", label: "Family Care Plan", group: "Planning" },
  { key: "consent", label: "Consent Record", group: "Planning" },
  { key: "cow1", label: "COW 1 Community Work Plan", group: "Planning" },
  { key: "process_note", label: "CW 11 Process Notes", group: "Process notes" },
  { key: "cow2_note", label: "COW 2 Community Process Note", group: "Process notes" },
  { key: "site_visit", label: "Site Visit Form", group: "Process notes" },
  { key: "evaluation", label: "CW 12 Evaluation", group: "Process notes" },
  { key: "group_work", label: "GRW Group Work Session", group: "Process notes" },
  { key: "referral", label: "CW 04B External Referral", group: "Referral & health" },
  { key: "hiv_risk", label: "HIV Risk Assessment", group: "Referral & health" },
  { key: "hivstat", label: "Child HIVSTAT Record", group: "Referral & health" },
  { key: "form22", label: "Form 22 Protection Incident", group: "Referral & health" },
  { key: "educational", label: "Educational Progress Record", group: "Reports" },
  { key: "monthly_report", label: "C06 Monthly Services Report", group: "Reports" },
  { key: "success_story", label: "Success Story", group: "Reports" },
  { key: "termination", label: "CW 13 Termination Report", group: "Closure" },
  { key: "exit", label: "Family Exit Form", group: "Closure" },
];

// Forms suitable for batch printing across many households.
export const BATCH_FORMS = [
  "checklist", "intake", "monthly_report", "family_care_plan", "educational", "full",
];

// Open a server-rendered DSD print view in a new tab. Auth token is passed as a
// query param so the browser tab can load it directly; `auto=1` triggers the
// print dialog on load.
export function printForm(form, { householdId, householdIds, org, auto = true, assessmentId } = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const qs = new URLSearchParams();
  qs.set("token", token || "");
  if (org) qs.set("org", org);
  if (auto) qs.set("auto", "1");
  if (assessmentId) qs.set("assessment_id", assessmentId);
  if (householdId) qs.set("household_id", householdId);
  if (householdIds && householdIds.length) qs.set("household_ids", householdIds.join(","));
  window.open(`${BACKEND_URL}/api/print/${form}/?${qs.toString()}`, "_blank", "noopener");
}

// Open the household activity timeline print view.
export function printTimeline(householdId) {
  const token = localStorage.getItem(TOKEN_KEY);
  const qs = new URLSearchParams({ token: token || "", auto: "1", household_id: householdId });
  window.open(`${BACKEND_URL}/api/print/timeline/?${qs.toString()}`, "_blank", "noopener");
}

// Open a service-delivery report print view.
// report: 'household' | 'monthly' | 'missed'
export function printServiceReport({ report = "household", householdId, month } = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const qs = new URLSearchParams({ token: token || "", auto: "1", report });
  if (householdId) qs.set("household_id", householdId);
  if (month) qs.set("month", month);
  window.open(`${BACKEND_URL}/api/print/service-report/?${qs.toString()}`, "_blank", "noopener");
}
