"""
Tests for iteration 2 additions:
1. Code Pickers (CW06/CW10) via /api/choices/
2. Print Center batch print
3. Structured Assessment CW09 CRUD
4. Signature Sign-off on checklist
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


@pytest.fixture(scope="module")
def cap_h(tokens):
    return {"Authorization": f"Token {tokens['capturer']}"}


@pytest.fixture(scope="module")
def households(admin_h):
    r = requests.get(f"{API}/households/?page_size=5", headers=admin_h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    return data.get("results", data) if isinstance(data, dict) else data


# ---- 1. Code Pickers ----
class TestCodePickers:
    def test_choices_has_codes(self, admin_h):
        r = requests.get(f"{API}/choices/", headers=admin_h, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "problem_codes" in data and len(data["problem_codes"]) >= 90
        assert "intervention_codes" in data and len(data["intervention_codes"]) >= 50
        assert "risk_level" in data and len(data["risk_level"]) >= 3
        # each entry has value/label
        pc0 = data["problem_codes"][0]
        assert "value" in pc0 and "label" in pc0

    def test_process_note_with_codes_persists(self, admin_h, households):
        hid = households[0]["id"]
        payload = {
            "household": hid,
            "purpose": "TEST_ code picker",
            "outcome": "TEST_ out",
            "engagement_type": "phone",
            "problem_code": "P1.1",
            "intervention_code": "I1.1",
        }
        r = requests.post(f"{API}/process-notes/", json=payload, headers=admin_h, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]
        note = r.json()
        nid = note["id"]
        # verify persistence via GET
        g = requests.get(f"{API}/process-notes/{nid}/", headers=admin_h, timeout=15)
        assert g.status_code == 200
        gd = g.json()
        assert gd.get("problem_code") == "P1.1"
        assert gd.get("intervention_code") == "I1.1"
        requests.delete(f"{API}/process-notes/{nid}/", headers=admin_h, timeout=15)


# ---- 2. Print Center ----
class TestPrintCenter:
    def test_batch_print_multiple(self, admin_h, households):
        ids = ",".join(str(h["id"]) for h in households[:3])
        r = requests.get(f"{API}/print/checklist/?household_ids={ids}", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()
        # each hh org_number should appear
        for h in households[:3]:
            org = h.get("org_number", "")
            if org:
                assert org.lower() in r.text.lower(), f"Missing {org}"

    def test_batch_print_supervisor(self, sup_h, households):
        ids = ",".join(str(h["id"]) for h in households[:2])
        r = requests.get(f"{API}/print/checklist/?household_ids={ids}", headers=sup_h, timeout=30)
        assert r.status_code == 200


# ---- 3. Assessments CW09 ----
class TestAssessments:
    def test_assessment_create_update_flow(self, admin_h, households):
        hid = households[0]["id"]
        # cleanup existing
        r0 = requests.get(f"{API}/assessments/?household={hid}", headers=admin_h, timeout=15)
        if r0.status_code == 200:
            existing = r0.json().get("results", r0.json()) if isinstance(r0.json(), dict) else r0.json()
            for a in existing or []:
                requests.delete(f"{API}/assessments/{a['id']}/", headers=admin_h, timeout=15)

        payload = {
            "household": hid,
            "overview_situation": "TEST_ overview",
            "identified_needs": "TEST_ needs",
            "risk_level": "High",
            "problem_codes": "P1.1, P1.2",
        }
        r = requests.post(f"{API}/assessments/", json=payload, headers=admin_h, timeout=15)
        assert r.status_code in (200, 201), r.text[:400]
        aid = r.json()["id"]

        # GET verify
        g = requests.get(f"{API}/assessments/{aid}/", headers=admin_h, timeout=15)
        assert g.status_code == 200
        assert g.json().get("overview_situation") == "TEST_ overview"
        assert g.json().get("risk_level") == "High"

        # PUT update
        u = requests.put(
            f"{API}/assessments/{aid}/",
            json={**payload, "overview_situation": "TEST_ updated"},
            headers=admin_h, timeout=15,
        )
        assert u.status_code in (200, 202), u.text[:300]

        g2 = requests.get(f"{API}/assessments/{aid}/", headers=admin_h, timeout=15)
        assert g2.json().get("overview_situation") == "TEST_ updated"

        # Print CW09 pre-filled
        p = requests.get(f"{API}/print/assessment/?household_id={hid}", headers=admin_h, timeout=30)
        assert p.status_code == 200
        assert "TEST_ updated" in p.text or "test_ updated" in p.text.lower()

        requests.delete(f"{API}/assessments/{aid}/", headers=admin_h, timeout=15)


# ---- 4. Signature Sign-off ----
class TestSignOff:
    def test_signoff_permission_denied_for_caseworker(self, cw_h, households):
        hid = households[0]["id"]
        r = requests.post(f"{API}/households/{hid}/sign_checklist/",
                          json={"sacssp": "SACSSP-CW-TEST"}, headers=cw_h, timeout=15)
        assert r.status_code in (403, 401), f"Caseworker unexpectedly allowed: {r.status_code}"

    def test_signoff_permission_denied_for_capturer(self, cap_h, households):
        hid = households[0]["id"]
        r = requests.post(f"{API}/households/{hid}/sign_checklist/",
                          json={"sacssp": "SACSSP-CAP-TEST"}, headers=cap_h, timeout=15)
        assert r.status_code in (403, 401)

    def test_signoff_supervisor_stamps_checklist(self, sup_h, households):
        hid = households[1]["id"]
        r = requests.post(f"{API}/households/{hid}/sign_checklist/",
                          json={"sacssp": "SACSSP-SUP-9999"}, headers=sup_h, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]
        # print checklist and verify stamp appears
        p = requests.get(f"{API}/print/checklist/?household_id={hid}", headers=sup_h, timeout=30)
        assert p.status_code == 200
        body = p.text
        assert "SACSSP-SUP-9999" in body, "SACSSP not stamped on printed checklist"
