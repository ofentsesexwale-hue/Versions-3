"""
Backend tests for OVC CaseFile: auth, print/export, households ordering,
timeline, verification_count, bulk_reassign, process notes.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

API = f"{BASE_URL}/api"

CREDS = {
    "admin": "admin123",
    "supervisor": "supervisor123",
    "caseworker": "caseworker123",
    "caseworker2": "caseworker123",
    "capturer": "capturer123",
}

FORMS = [
    "checklist", "intake", "reporter", "assessment", "family_care_plan",
    "educational", "referral", "process_note", "cow2_note", "termination",
    "site_visit", "exit", "success_story", "monthly_report", "hiv_risk", "full",
]

FORM_TITLE_HINTS = {
    "checklist": ["checklist", "case file"],
    "intake": ["cw", "intake"],
    "reporter": ["cw", "reporter"],
    "assessment": ["cw", "assessment"],
    "family_care_plan": ["care plan", "family"],
    "educational": ["educational"],
    "referral": ["referral", "cw"],
    "process_note": ["process", "cw 11"],
    "cow2_note": ["cow", "community"],
    "termination": ["termination", "cw 13"],
    "site_visit": ["site visit"],
    "exit": ["exit"],
    "success_story": ["success"],
    "monthly_report": ["monthly", "c06"],
    "hiv_risk": ["hiv"],
    "full": ["case file"],
}


def _login(username):
    r = requests.post(f"{API}/auth/login/", json={"username": username, "password": CREDS[username]}, timeout=15)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def tokens():
    return {u: _login(u) for u in CREDS}


@pytest.fixture(scope="session")
def admin_headers(tokens):
    return {"Authorization": f"Token {tokens['admin']}"}


@pytest.fixture(scope="session")
def a_household(admin_headers):
    r = requests.get(f"{API}/households/?page_size=5", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    results = data.get("results", data) if isinstance(data, dict) else data
    assert results, "No households seeded"
    return results[0]


# ---------- AUTH ----------
class TestAuth:
    @pytest.mark.parametrize("user", list(CREDS.keys()))
    def test_login_each_role(self, user):
        tok = _login(user)
        r = requests.get(f"{API}/auth/me/", headers={"Authorization": f"Token {tok}"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("username") == user

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login/", json={"username": "admin", "password": "wrong"}, timeout=10)
        assert r.status_code in (400, 401)


# ---------- CORE APIVIEWS ----------
class TestCoreAPIs:
    def test_dashboard(self, admin_headers):
        r = requests.get(f"{API}/dashboard/", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_choices(self, admin_headers):
        r = requests.get(f"{API}/choices/", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_users_list(self, admin_headers):
        r = requests.get(f"{API}/users/", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))


# ---------- PRINT / EXPORT ----------
class TestPrintExport:
    @pytest.mark.parametrize("form", FORMS)
    def test_print_form_header_token(self, form, admin_headers, a_household):
        hh_id = a_household["id"]
        r = requests.get(
            f"{API}/print/{form}/?household_id={hh_id}",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, f"{form}: {r.status_code} - {r.text[:200]}"
        assert "text/html" in r.headers.get("Content-Type", "").lower()
        body = r.text.lower()
        # Contains DSD-hint OR at least meaningful HTML
        assert "<html" in body or "<!doctype" in body
        # populated data (org_number typically 'TEST-xxxx')
        org_no = a_household.get("org_number", "")
        if org_no:
            assert org_no.lower() in body, f"{form} missing org_number {org_no}"

    def test_print_query_token(self, tokens, a_household):
        # Test ?token= param method
        r = requests.get(
            f"{API}/print/full/?household_id={a_household['id']}&token={tokens['admin']}",
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()

    def test_print_unauthorized(self, a_household):
        r = requests.get(f"{API}/print/full/?household_id={a_household['id']}", timeout=15)
        assert r.status_code in (401, 403)

    def test_print_invalid_form(self, admin_headers, a_household):
        r = requests.get(
            f"{API}/print/badform_zzz/?household_id={a_household['id']}",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code in (400, 404)


# ---------- HOUSEHOLDS ORDERING / COMPLETENESS ----------
class TestHouseholdOrdering:
    def test_ordering_by_completeness(self, admin_headers):
        r = requests.get(f"{API}/households/?ordering=completeness&page_size=20", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        assert len(results) >= 2
        percents = []
        for h in results:
            cp = h.get("checklist_progress") or {}
            if isinstance(cp, dict) and "percent" in cp:
                percents.append(cp["percent"])
        if len(percents) >= 2:
            assert percents == sorted(percents), f"Not ascending: {percents}"

    def test_verification_count(self, admin_headers):
        r = requests.get(f"{API}/households/verification_count/", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "total" in data or "count" in data or isinstance(data, dict)


# ---------- TIMELINE ----------
class TestTimeline:
    def test_household_timeline(self, admin_headers, a_household):
        r = requests.get(f"{API}/households/{a_household['id']}/timeline/", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # list or paginated dict
        assert isinstance(data, (list, dict))


# ---------- PROCESS NOTES CRUD ----------
class TestProcessNotes:
    def test_process_note_crud(self, admin_headers, a_household):
        payload = {
            "household": a_household["id"],
            "purpose": "TEST_ purpose entry",
            "outcome": "TEST_ outcome entry",
            "engagement_type": "phone",
        }
        r = requests.post(f"{API}/process-notes/", json=payload, headers=admin_headers, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]
        note = r.json()
        nid = note.get("id")
        assert nid

        # List
        r2 = requests.get(f"{API}/process-notes/?household={a_household['id']}", headers=admin_headers, timeout=15)
        assert r2.status_code == 200

        # Delete
        r3 = requests.delete(f"{API}/process-notes/{nid}/", headers=admin_headers, timeout=15)
        assert r3.status_code in (200, 204)


# ---------- BULK REASSIGN ----------
class TestBulkReassign:
    def test_bulk_reassign_permission_forbidden(self, tokens, a_household):
        # capturer/caseworker should be forbidden
        r = requests.post(
            f"{API}/households/bulk_reassign/",
            json={"household_ids": [a_household["id"]], "assigned_to": 1},
            headers={"Authorization": f"Token {tokens['caseworker']}"},
            timeout=15,
        )
        assert r.status_code in (403, 401)

    def test_bulk_reassign_admin(self, tokens, admin_headers):
        # Find caseworker + caseworker2 user ids
        r = requests.get(f"{API}/users/", headers=admin_headers, timeout=15)
        users = r.json()
        if isinstance(users, dict):
            users = users.get("results", [])
        by_name = {u["username"]: u["id"] for u in users if "username" in u and "id" in u}
        cw1 = by_name.get("caseworker")
        cw2 = by_name.get("caseworker2")
        if not (cw1 and cw2):
            pytest.skip("caseworker users not found in /users/")

        # Get households assigned to caseworker
        r = requests.get(f"{API}/households/?assigned_to={cw1}&page_size=3", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        if not results:
            pytest.skip("No households assigned to caseworker")
        hh_ids = [h["id"] for h in results[:1]]

        # Reassign
        r2 = requests.post(
            f"{API}/households/bulk_reassign/",
            json={"household_ids": hh_ids, "to_user": cw2},
            headers=admin_headers, timeout=15,
        )
        assert r2.status_code in (200, 202), r2.text[:300]

        # Verify
        r3 = requests.get(f"{API}/households/{hh_ids[0]}/", headers=admin_headers, timeout=15)
        assert r3.status_code == 200
        det = r3.json()
        assigned = det.get("assigned_to")
        if isinstance(assigned, list):
            ids = [a.get("id") if isinstance(a, dict) else a for a in assigned]
        elif isinstance(assigned, dict):
            ids = [assigned.get("id")]
        elif assigned is not None:
            ids = [assigned]
        else:
            ids = det.get("assigned_to_ids") or []
        assert cw2 in ids, f"cw2 {cw2} not in {ids}"

        # Revert
        requests.post(
            f"{API}/households/bulk_reassign/",
            json={"household_ids": hh_ids, "to_user": cw1},
            headers=admin_headers, timeout=15,
        )
