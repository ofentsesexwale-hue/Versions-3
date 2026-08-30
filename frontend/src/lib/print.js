import { TOKEN_KEY } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// The organisation name printed in form headers. Central so it stays consistent.
export const ORG_NAME = "OVC Organisation";

// Per-household DSD forms (official Department of Social Development templates).
export const DSD_FORMS = [
  { key: "full", label: "Full Case File", group: "Case file" },
  { key: "checklist", label: "Case File Checklist", group: "Case file" },
  { key: "intake", label: "CW 05 Intake Form", group: "Intake & assessment" },
  { key: "reporter", label: "CW 02 Reporter Form", group: "Intake & assessment" },
  { key: "assessment", label: "CW 09 Assessment, Planning & Contracting", group: "Intake & assessment" },
  { key: "family_care_plan", label: "Family Care Plan", group: "Planning" },
  { key: "process_note", label: "CW 11 Process Notes", group: "Process notes" },
  { key: "cow2_note", label: "COW 2 Community Process Note", group: "Process notes" },
  { key: "site_visit", label: "Site Visit Form", group: "Process notes" },
  { key: "referral", label: "CW 04B External Referral", group: "Referral & health" },
  { key: "hiv_risk", label: "HIV Risk Assessment", group: "Referral & health" },
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
export function printForm(form, { householdId, householdIds, org, auto = true } = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const qs = new URLSearchParams();
  qs.set("token", token || "");
  qs.set("org", org || ORG_NAME);
  if (auto) qs.set("auto", "1");
  if (householdId) qs.set("household_id", householdId);
  if (householdIds && householdIds.length) qs.set("household_ids", householdIds.join(","));
  window.open(`${BACKEND_URL}/api/print/${form}/?${qs.toString()}`, "_blank", "noopener");
}
