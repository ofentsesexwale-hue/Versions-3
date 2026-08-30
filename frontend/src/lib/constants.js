export const ROLE_LABELS = {
  "data-capturer": "Data Capturer",
  "case-worker": "Case Worker (SSP)",
  supervisor: "Supervisor (QA)",
  admin: "Administrator",
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
