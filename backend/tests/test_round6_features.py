"""Round-6 tests: Version lock, Login tagline, Timeline export, Completeness chart, Services."""
import os
import pytest
import requests
from datetime import date, timedelta

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login/", json={"username": username, "password": password})
    assert r.status_code == 200, f"login {username} -> {r.status_code} {r.text}"
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


def _h(token):
    return {"Authorization": f"Token {token}"}


# ----------------------- Version Lock -----------------------
class TestVersionLock:
    def test_version_field_present(self, admin_token):
        r = requests.get(f"{API}/households/60/", headers=_h(admin_token))
        assert r.status_code == 200
        assert "version" in r.json()

    def test_stale_version_returns_409(self, admin_token):
        r = requests.get(f"{API}/households/60/", headers=_h(admin_token))
        hh = r.json()
        stale = (hh.get("version") or 1) - 1
        r2 = requests.patch(f"{API}/households/60/", headers=_h(admin_token),
                            json={"version": stale, "street": hh.get("street", "x")})
        assert r2.status_code == 409, f"expected 409 got {r2.status_code} {r2.text}"
        assert "modified" in r2.text.lower() or "another" in r2.text.lower()

    def test_correct_version_increments(self, admin_token):
        r = requests.get(f"{API}/households/60/", headers=_h(admin_token))
        hh = r.json()
        cur = hh["version"]
        r2 = requests.patch(f"{API}/households/60/", headers=_h(admin_token),
                            json={"version": cur, "street": hh.get("street", "test") or "test"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["version"] == cur + 1


# ----------------------- Login Tagline -----------------------
class TestLoginTagline:
    def test_site_config_put_and_branding(self, admin_token):
        tagline = "TEST tagline round6"
        r = requests.put(f"{API}/site-config/", headers=_h(admin_token),
                         json={"login_tagline": tagline})
        assert r.status_code in (200, 201), r.text
        # Public branding
        r2 = requests.get(f"{API}/branding/")
        assert r2.status_code == 200
        assert r2.json().get("login_tagline") == tagline

    def test_site_config_requires_admin(self, caseworker_token):
        r = requests.put(f"{API}/site-config/", headers=_h(caseworker_token),
                         json={"login_tagline": "hack"})
        assert r.status_code in (401, 403)


# ----------------------- Timeline Export -----------------------
class TestTimelineExport:
    def test_print_timeline_html(self, admin_token):
        r = requests.get(f"{API}/households/", headers=_h(admin_token))
        hid = (r.json().get("results", r.json()))[0]["id"]
        r2 = requests.get(f"{API}/print/timeline/", params={"household_id": hid, "token": admin_token})
        assert r2.status_code == 200, r2.text
        assert "text/html" in r2.headers.get("content-type", "")
        assert "<html" in r2.text.lower()


# ----------------------- Completeness Chart -----------------------
class TestCompleteness:
    def test_dashboard_bands(self, supervisor_token):
        r = requests.get(f"{API}/dashboard/", headers=_h(supervisor_token))
        assert r.status_code == 200
        bands = r.json().get("completeness_bands")
        assert bands is not None, r.json()
        for k in ("ready", "in_progress", "needs_attention"):
            assert k in bands

    def test_band_filter(self, supervisor_token):
        r = requests.get(f"{API}/households/", headers=_h(supervisor_token),
                         params={"band": "in_progress"})
        assert r.status_code == 200


# ----------------------- Services -----------------------
class TestServices:
    def test_service_create_future_date_400(self, admin_token):
        r = requests.get(f"{API}/households/", headers=_h(admin_token))
        hid = (r.json().get("results", r.json()))[0]["id"]
        # get a service type
        c = requests.get(f"{API}/choices/", headers=_h(admin_token)).json()
        st = None
        for key in ("service_types", "service_type"):
            if key in c and c[key]:
                st = c[key][0]
                break
        if isinstance(st, dict):
            st = st.get("value") or st.get("key") or st.get("code")
        assert st, f"no service type in choices: {list(c.keys())}"
        future = (date.today() + timedelta(days=10)).isoformat()
        r2 = requests.post(f"{API}/services/", headers=_h(admin_token),
                           json={"household": hid, "service_type": st, "service_date": future})
        assert r2.status_code == 400, r2.text

    def test_service_create_today(self, admin_token):
        r = requests.get(f"{API}/households/", headers=_h(admin_token))
        hid = (r.json().get("results", r.json()))[0]["id"]
        c = requests.get(f"{API}/choices/", headers=_h(admin_token)).json()
        st = None
        for key in ("service_types", "service_type"):
            if key in c and c[key]:
                st = c[key][0]
                break
        if isinstance(st, dict):
            st = st.get("value") or st.get("key") or st.get("code")
        r2 = requests.post(f"{API}/services/", headers=_h(admin_token),
                           json={"household": hid, "service_type": st, "service_date": date.today().isoformat()})
        assert r2.status_code in (200, 201), r2.text

    def test_bulk_log(self, admin_token):
        r = requests.get(f"{API}/households/", headers=_h(admin_token))
        results = r.json().get("results", r.json())
        ids = [h["id"] for h in results[:3]]
        c = requests.get(f"{API}/choices/", headers=_h(admin_token)).json()
        st = None
        for key in ("service_types", "service_type"):
            if key in c and c[key]:
                st = c[key][0]
                break
        if isinstance(st, dict):
            st = st.get("value") or st.get("key") or st.get("code")
        r2 = requests.post(f"{API}/services/bulk_log/", headers=_h(admin_token),
                           json={"household_ids": ids, "service_type": st,
                                 "service_date": date.today().isoformat()})
        assert r2.status_code in (200, 201), r2.text

    def test_stats(self, supervisor_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(supervisor_token))
        assert r.status_code == 200
        j = r.json()
        # expect served/total keys somewhere
        assert isinstance(j, dict)

    def test_monthly_detail(self, supervisor_token):
        r = requests.get(f"{API}/services/monthly_detail/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert "missed" in r.json()

    def test_print_service_reports(self, admin_token):
        r = requests.get(f"{API}/households/", headers=_h(admin_token))
        hid = (r.json().get("results", r.json()))[0]["id"]
        for params in [
            {"report": "household", "household_id": hid, "token": admin_token},
            {"report": "monthly", "token": admin_token},
            {"report": "missed", "token": admin_token},
        ]:
            r2 = requests.get(f"{API}/print/service-report/", params=params)
            assert r2.status_code == 200, f"{params} -> {r2.status_code} {r2.text[:200]}"


# ----------------------- RBAC: caseworker service create -----------------------
class TestServiceRBAC:
    def test_caseworker_cannot_log_unassigned(self, caseworker_token, admin_token):
        # find a household NOT assigned to caseworker
        me = requests.get(f"{API}/auth/me/", headers=_h(caseworker_token)).json()
        my_id = me.get("id") or me.get("user", {}).get("id")
        r = requests.get(f"{API}/households/", headers=_h(admin_token)).json()
        results = r.get("results", r)
        target = None
        for h in results:
            assigned = h.get("assigned_to_ids") or h.get("assigned_to") or []
            if isinstance(assigned, list):
                if my_id not in assigned:
                    target = h["id"]
                    break
            elif assigned != my_id:
                target = h["id"]
                break
        if target is None:
            pytest.skip("No unassigned household found")
        c = requests.get(f"{API}/choices/", headers=_h(admin_token)).json()
        st = None
        for key in ("service_types", "service_type"):
            if key in c and c[key]:
                st = c[key][0]
                break
        if isinstance(st, dict):
            st = st.get("value") or st.get("key") or st.get("code")
        r2 = requests.post(f"{API}/services/", headers=_h(caseworker_token),
                           json={"household": target, "service_type": st,
                                 "service_date": date.today().isoformat()})
        # server should block; accept 403 or 400
        assert r2.status_code in (400, 403), f"expected block, got {r2.status_code} {r2.text}"
