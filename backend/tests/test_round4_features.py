"""Round-4 polish tests: timeline sign-off, logo (org), assessment versions, cover signatures."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"


def _login(u, p):
    r = requests.post(f"{API}/auth/login/", json={"username": u, "password": p}, timeout=30)
    assert r.status_code == 200, f"login {u} -> {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin", "admin123")


@pytest.fixture(scope="module")
def supervisor_token():
    return _login("supervisor", "supervisor123")


@pytest.fixture(scope="module")
def caseworker_token():
    return _login("caseworker", "caseworker123")


def _h(tok):
    return {"Authorization": f"Token {tok}"}


# --- Timeline Sign-off ------------------------------------------------------
class TestTimelineSignoff:
    def test_timeline_contains_signoff_entry(self, supervisor_token):
        r = requests.get(f"{API}/households/59/timeline/", headers=_h(supervisor_token), timeout=30)
        assert r.status_code == 200
        entries = r.json()
        texts = [e.get("target_description", "") for e in entries]
        assert any("Signed off checklist for Household #59" in t for t in texts), \
            f"Signoff entry missing. Got: {texts[:10]}"


# --- Organisation Logo ------------------------------------------------------
class TestOrganisationLogo:
    def test_organisation_get(self, admin_token):
        r = requests.get(f"{API}/organisation/", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "logo" in data  # may be null/empty when not uploaded

    def test_upload_and_fetch_logo(self, admin_token):
        # Upload a tiny PNG (1x1 red)
        png_bytes = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
            "0000000D49444154789C63F80F0000010101007D8AF7370000000049454E44AE426082"
        )
        files = {"logo": ("test.png", io.BytesIO(png_bytes), "image/png")}
        data = {"name": "Ubuntu Care NPO"}
        r = requests.put(f"{API}/organisation/", headers=_h(admin_token), files=files, data=data, timeout=30)
        assert r.status_code in (200, 202), f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("logo"), f"No logo in response: {body}"
        # Fetch org and confirm logo path
        r2 = requests.get(f"{API}/organisation/", headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200
        logo = r2.json().get("logo")
        assert logo, "Org logo missing after upload"
        # Try to fetch the media file itself
        logo_url = logo if logo.startswith("http") else f"{BASE_URL}{logo}"
        r3 = requests.get(logo_url, timeout=30)
        assert r3.status_code == 200, f"Logo media file not served: {r3.status_code} at {logo_url}"


# --- Assessment Versions ----------------------------------------------------
class TestAssessmentVersions:
    def test_two_versions_for_hh60(self, supervisor_token):
        r = requests.get(f"{API}/assessments/", headers=_h(supervisor_token),
                         params={"household": 60, "page_size": 50}, timeout=30)
        assert r.status_code == 200
        results = r.json().get("results", r.json() if isinstance(r.json(), list) else [])
        assert len(results) >= 2, f"Expected >=2 assessments for hh60, got {len(results)}"

    def test_print_specific_version(self, supervisor_token):
        r = requests.get(f"{API}/assessments/", headers=_h(supervisor_token),
                         params={"household": 60, "page_size": 50}, timeout=30)
        results = r.json().get("results", [])
        assert len(results) >= 2
        aid = results[0]["id"]
        pr = requests.get(f"{API}/print/assessment/", headers=_h(supervisor_token),
                          params={"household_id": 60, "assessment_id": aid}, timeout=30)
        assert pr.status_code == 200
        assert "html" in pr.headers.get("content-type", "").lower() or "<html" in pr.text.lower()

    def test_new_assessment_creates_version(self, supervisor_token):
        payload = {
            "household": 60,
            "overview_situation": "TEST_R4 version C",
            "problem_codes": "1.1",
        }
        r = requests.post(f"{API}/assessments/", headers=_h(supervisor_token), json=payload, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        new_id = r.json().get("id")
        assert new_id
        # Fetch list, count should have gone up
        r2 = requests.get(f"{API}/assessments/", headers=_h(supervisor_token),
                          params={"household": 60, "page_size": 50}, timeout=30)
        ids = [x["id"] for x in r2.json().get("results", [])]
        assert new_id in ids
        assert len(ids) >= 3
        # Cleanup
        requests.delete(f"{API}/assessments/{new_id}/", headers=_h(supervisor_token), timeout=30)


# --- Cover Signatures -------------------------------------------------------
class TestCoverSignatures:
    def test_batch_cover_has_signature_lines(self, supervisor_token):
        r = requests.get(f"{API}/print/checklist/", headers=_h(supervisor_token),
                         params={"household_ids": "59,60"}, timeout=30)
        assert r.status_code == 200
        html = r.text
        assert "Prepared by:" in html, "Missing 'Prepared by:' in batch cover"
        assert "Supervisor name" in html or "Supervisor name & signature" in html, \
            "Missing supervisor signature line in batch cover"

    def test_batch_full_cover(self, supervisor_token):
        r = requests.get(f"{API}/print/full/", headers=_h(supervisor_token),
                         params={"household_ids": "59,60"}, timeout=30)
        assert r.status_code == 200
        assert "Prepared by:" in r.text
        assert "Supervisor name" in r.text


# --- Regression: prints still 200 -------------------------------------------
@pytest.mark.parametrize("form", ["intake", "checklist", "assessment", "process_note", "referral"])
def test_print_regression(form, supervisor_token):
    r = requests.get(f"{API}/print/{form}/", headers=_h(supervisor_token),
                     params={"household_id": 60}, timeout=30)
    assert r.status_code == 200, f"{form} -> {r.status_code}"
