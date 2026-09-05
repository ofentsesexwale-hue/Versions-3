export const ROLE_LABELS = {
  "data-capturer": "Data capturer",
  "case-worker": "Case worker (SSP)",
  cycw: "CYCW",
  auxiliary: "Auxiliary",
  caregiver: "Caregiver",
  "caregiver-epwp": "Caregiver(E.P.W.P)",
  "epwp-coordinator": "E.P.W.P Coordinator",
  "poverty-alleviator-coordinator": "Poverty Alleviator Coordinator",
  supervisor: "Supervisor (QA)",
  admin: "Administrator",
};

export const LIVE_OFFICE_TITLES = [
  "epwp-coordinator",
  "poverty-alleviator-coordinator",
  "cycw",
  "auxiliary",
  "caregiver",
  "caregiver-epwp",
  "data-capturer",
  "supervisor",
  "admin",
];

export const ROLE_PERMISSIONS = {
  admin: "Full live office: all files, staff logins, organisation, and audit.",
  supervisor: "All files, quality sign-off, and caseload reassignment. Cannot add staff.",
  "epwp-coordinator": "All files for E.P.W.P coordination. Capture and assign caseload. No staff logins or sign-off.",
  "poverty-alleviator-coordinator": "All files for poverty-alleviation coordination. Capture and assign caseload. No staff logins or sign-off.",
  cycw: "Own caseload: open files, capture caregivers and children, visits, and services.",
  "case-worker": "Own caseload (training title). Same field permissions as a CYCW.",
  auxiliary: "Own caseload: support visits, services, and file capture. No sign-off or staff.",
  "caregiver-epwp": "Own caseload as an E.P.W.P caregiver: visits, services, and file capture. No sign-off or staff.",
  "data-capturer": "All files for capturing. No sign-off, reassignment, or staff.",
  caregiver: "View the household file linked to this login. Cannot change office records.",
};

export const FIELD_WORKER_ROLES = [
  "case-worker",
  "cycw",
  "auxiliary",
  "caregiver-epwp",
  "epwp-coordinator",
  "poverty-alleviator-coordinator",
];

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
  intake_form: "1. Intake Forms",
  family_care_plan: "2. Family Care Plans",
  vital_document: "3. Vital Documents",
  process_note: "4. Process Notes",
  school_report: "5. School Visit Reports",
  referral_form: "6. Referral Forms",
  success_story: "7. Success Stories",
  monthly_report: "8. Monthly Reports",
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