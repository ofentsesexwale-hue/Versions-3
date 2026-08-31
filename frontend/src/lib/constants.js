export const ROLE_LABELS = {
  "data-capturer": "Data capturer",
  "case-worker": "Case worker (SSP)",
  cycw: "CYCW",
  auxiliary: "Auxiliary",
  caregiver: "Caregiver",
  supervisor: "Supervisor (QA)",
  admin: "Administrator",
};

export const LIVE_OFFICE_TITLES = [
  "cycw",
  "auxiliary",
  "caregiver",
  "data-capturer",
  "supervisor",
  "admin",
];

export const ROLE_PERMISSIONS = {
  admin: "Full live office: all files, staff logins, organisation, and audit.",
  supervisor: "All files, quality sign-off, and caseload reassignment. Cannot add staff.",
  cycw: "Own caseload: open files, capture caregivers and children, visits, and services.",
  "case-worker": "Own caseload (training title). Same field permissions as a CYCW.",
  auxiliary: "Own caseload: support visits, services, and file capture. No sign-off or staff.",
  "data-capturer": "All files for capturing. No sign-off, reassignment, or staff.",
  caregiver: "View the household file linked to this login. Cannot change office records.",
};

export const FIELD_WORKER_ROLES = ["case-worker", "cycw", "auxiliary"];

export function isFieldWorker(role) {
  return FIELD_WORKER_ROLES.includes(role);
}

export const CASE_STATUS_LABELS = {
  open: "Open",
  graduated: "Graduated",
  transferred: "Transferred",
  lost_to_follow_up: "Lost to follow-up",
  closed: "Closed",
};

export const CATEGORY_LABELS = {
  intake_form: "Intake Forms",
  family_care_plan: "Family Care Plans",
  vital_document: "Vital Documents",
  process_note: "Process Notes",
  school_report: "School Visit Reports",
  referral_form: "Referral Forms",
  success_story: "Success Stories",
  monthly_report: "Monthly Reports",
};

export const CATEGORY_ORDER = [
  "intake_form",
  "family_care_plan",
  "vital_document",
  "process_note",
  "school_report",
  "referral_form",
  "success_story",
  "monthly_report",
];

export function formatDate(value) {
  if (!value) return "\u2014";
  try {
    const d = new Date(value);
    return d.toLocaleDateString("en-ZA", { year: "numeric", month: "short", day: "numeric" });
  } catch (e) {
    return value;
  }
}

export function formatDateTime(value) {
  if (!value) return "\u2014";
  try {
    const d = new Date(value);
    return d.toLocaleString("en-ZA", {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch (e) {
    return value;
  }
}
