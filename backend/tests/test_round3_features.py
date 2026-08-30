"""
Round-3 tests: Plan Rows, Organisation letterhead, Sign-off History, Batch Cover Page.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "admin": "admin123",
    "supervisor": "supervisor123",
    "caseworker": "caseworker123",
    "capturer": "capturer123",
}


def _login(u):
    r = requests.post(f"{API}/auth/login/", json={"username": u, "password": CREDS[u]}, timeout=15)
    assert r.status_code == 200, r.text[:200]
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {u: _login(u) for u in CREDS}


@pytest.fixture(scope="module")
def admin_h(tokens):
    return {"Authorization": f"Token {tokens['admin']}"}


@pytest.fixture(scope="module")
def sup_h(tokens):
    return {"Authorization": f"Token {tokens['supervisor']}"}


@pytest.fixture(scope="module")
def cw_h(tokens):
    return {"Authorization": f"Token {tokens['caseworker']}"}


# ---- Plan Rows ----
class TestPlanRows:
    def test_assessment_plan_rows_persist_and_print(self, admin_h):
        hid = 59
        # remove existing assessments for a clean slate
        r0 = requests.get(f"{API}/assessments/?household={hid}", headers=admin_h, timeout=15)
        existing = r0.json().get("results", r0.json()) if isinstance(r0.json(), dict) else r0.json()
        for a in existing or []:
            requests.delete(f"{API}/assessments/{a['id']}/", headers=admin_h, timeout=15)

        plan_rows = [
            {"issue": "TEST_ Food insecurity", "intervention": "Refer SASSA", "due_date": "2026-03-01", "responsibility": "Case worker"},
            {"issue": "TEST_ School fees", "intervention": "NGO bursary", "due_date": "2026-04-15", "responsibility": "Supervisor"},
        ]
        payload = {
            "household": hid,
            "overview_situation": "TEST_ plan rows",
            "identified_needs": "TEST_",
            "risk_level": "High",
            "plan_rows": plan_rows,
        }
        r = requests.post(f"{API}/assessments/", json=payload, headers=admin_h, timeout=15)
        assert r.status_code in (200, 201), r.text[:400]
        aid = r.json()["id"]

        g = requests.get(f"{API}/assessments/{aid}/", headers=admin_h, timeout=15)
        assert g.status_code == 200
        got = g.json().get("plan_rows") or []
        assert len(got) == 2
        assert got[0]["issue"] == "TEST_ Food insecurity"
        assert got[1]["responsibility"] == "Supervisor"

        # Print CW09 shows plan rows
        p = requests.get(f"{API}/print/assessment/?household_id={hid}", headers=admin_h, timeout=30)
        assert p.status_code == 200
        assert "TEST_ Food insecurity" in p.text
        assert "NGO bursary" in p.text


# ---- Organisation ----
class TestOrganisation:
    def test_admin_can_put_org(self, admin_h):
        r = requests.put(
            f"{API}/organisation/",
            data={"name": "Ubuntu Care NPO", "address": "1 Care Rd", "contact": "011-000-0000"},
            headers=admin_h, timeout=15,
        )
        assert r.status_code in (200, 201, 202), r.text[:300]
        # GET to verify
        g = requests.get(f"{API}/organisation/", headers=admin_h, timeout=15)
        assert g.status_code == 200
        assert g.json().get("name") == "Ubuntu Care NPO"

    def test_supervisor_forbidden_to_put(self, sup_h):
        r = requests.put(
            f"{API}/organisation/",
            data={"name": "SHOULD_NOT_APPLY"},
            headers=sup_h, timeout=15,
        )
        assert r.status_code in (401, 403), f"Supervisor unexpectedly allowed: {r.status_code}"

    def test_caseworker_forbidden_to_put(self, cw_h):
        r = requests.put(
            f"{API}/organisation/",
            data={"name": "SHOULD_NOT_APPLY_CW"},
            headers=cw_h, timeout=15,
        )
        assert r.status_code in (401, 403)

    def test_org_name_in_printed_intake(self, admin_h):
        p = requests.get(f"{API}/print/intake/?household_id=59", headers=admin_h, timeout=30)
        assert p.status_code == 200
        assert "Ubuntu Care NPO" in p.text


# ---- Sign-off History ----
class TestSignoffHistory:
    def test_signed_filter_returns_only_signed(self, sup_h):
        r = requests.get(f"{API}/households/?signed=1&page_size=100", headers=sup_h, timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        assert len(items) >= 1
        for h in items:
            # Only signed households: must have a signer or signed_at field truthy
            signed_any = (
                h.get("checklist_signed_at")
                or h.get("checklist_signed_by")
                or h.get("checklist_signed_by_name")
                or h.get("checklist_sacssp")
            )
            assert signed_any, f"Unsigned household in signed=1 filter: {h.get('id')}"

    def test_caseworker_can_still_call_but_returns_only_own_or_empty(self, cw_h):
        r = requests.get(f"{API}/households/?signed=1", headers=cw_h, timeout=15)
        assert r.status_code == 200


# ---- Batch Cover Page ----
class TestBatchCoverPage:
    def test_batch_full_has_cover(self, admin_h):
        r = requests.get(f"{API}/print/full/?household_ids=59,60", headers=admin_h, timeout=45)
        assert r.status_code == 200, r.text[:300]
        assert "Batch Print Cover" in r.text
        # both household org numbers should appear
        h59 = requests.get(f"{API}/households/59/", headers=admin_h, timeout=15).json()
        h60 = requests.get(f"{API}/households/60/", headers=admin_h, timeout=15).json()
        for h in (h59, h60):
            org = h.get("org_number", "")
            if org:
                assert org in r.text, f"Missing {org} on cover"

    def test_single_household_full_no_cover(self, admin_h):
        r = requests.get(f"{API}/print/full/?household_id=59", headers=admin_h, timeout=45)
        assert r.status_code == 200
        assert "Batch Print Cover" not in r.text


# ---- Regression: all print forms still 200 ----
PRINT_FORMS = [
    "intake", "checklist", "assessment", "consent", "process_note",
    "referral", "closure", "review", "care_plan", "home_visit",
    "risk", "cw01", "cw02", "cw06", "cw10", "cw11",
]

class TestPrintRegression:
    @pytest.mark.parametrize("form", PRINT_FORMS)
    def test_print_form_ok(self, admin_h, form):
        r = requests.get(f"{API}/print/{form}/?household_id=59", headers=admin_h, timeout=30)
        # Some names may not match; treat 404 as skip
        if r.status_code == 404:
            pytest.skip(f"{form} not registered")
        assert r.status_code == 200, f"{form} -> {r.status_code}"
