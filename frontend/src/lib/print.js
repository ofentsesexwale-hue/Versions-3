import { TOKEN_KEY } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// The organisation name/logo used on printed forms now comes from the backend
// Organisation profile; only pass `org` to override it explicitly.
export const ORG_NAME = "Sebueng Itumeleng";

// Per-household DSD forms (official Department of Social Development templates).
export const DSD_FORMS = [
  // Tree A reprint order — matches CHECKLIST_TEMPLATE / NPO Content Page.
  { key: "content_page", label: "Content Page", group: "1. Case file" },
  { key: "checklist", label: "NPO Check List", group: "1. Case file" },
  { key: "full", label: "Full Case File", group: "1. Case file" },
  { key: "c01", label: "C01 Household Details", group: "2. Intake Forms" },
  { key: "c02", label: "C02 Adult Assessment", group: "2. Intake Forms" },
  { key: "c03", label: "C03 Child Beneficiary Assessment", group: "2. Intake Forms" },
  { key: "intake", label: "CW 05 Intake Form", group: "2. Intake Forms" },
  { key: "family_care_plan", label: "Family Care Plan", group: "3. Family Care Plans" },
  { key: "consent", label: "HIV Consent / Child Assent", group: "3. Family Care Plans" },
  { key: "assessment", label: "CW 09 Assessment, Planning & Contracting", group: "3. Family Care Plans" },
  { key: "process_note", label: "CW 11 Process Notes", group: "4. Process Notes" },
  { key: "site_visit", label: "Site Visit Form", group: "4. Process Notes" },
  { key: "cow2_note", label: "COW 2 Community Process Note", group: "4. Process Notes" },
  { key: "evaluation", label: "CW 12 Evaluation", group: "4. Process Notes" },
  { key: "termination", label: "CW 13 Termination Report", group: "4. Process Notes" },
  { key: "exit", label: "Family Exit Form", group: "4. Process Notes" },
  { key: "educational", label: "Educational Progress Record", group: "5. School Visit Reports" },
  { key: "internal_referral", label: "CW 4a Internal Referral", group: "6. Referral Forms" },
  { key: "referral", label: "CW 4b External Referral", group: "6. Referral Forms" },
  { key: "client_referral", label: "Client Referral Form (HIV pack)", group: "6. Referral Forms" },
  { key: "success_story", label: "Success Story", group: "7. Success Stories" },
  { key: "monthly_report", label: "C06 Monthly Services Report", group: "8. Monthly Reports" },
  { key: "reporter", label: "CW 02 Reporter Form", group: "Office tools" },
  { key: "cow1", label: "COW 1 Community Work Plan", group: "Office tools" },
  { key: "group_work", label: "GRW Group Work Session", group: "Office tools" },
  { key: "hiv_risk", label: "HIV Risk Assessment", group: "Office tools" },
  { key: "hivstat", label: "HTS Tracking / Beneficiary Details", group: "Office tools" },
  { key: "form22", label: "Form 22 Protection Incident", group: "Office tools" },
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
