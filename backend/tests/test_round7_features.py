"""Round-7 tests: Service Trend chart, Beneficiary Reminders, CSV export, Race-safe versioning + regression."""
import csv
import io
import os
import pytest
import requests
from datetime import date

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


def _login(u, p):
    r = requests.post(f"{API}/auth/login/", json={"username": u, "password": p})
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


@pytest.fixture(scope="module")
def capturer_token():
    return _login("capturer", "capturer123")


def _h(t):
    return {"Authorization": f"Token {t}"}


# ---------------- Service Trend Chart ----------------
class TestServiceTrend:
    def test_stats_returns_trend_4_buckets(self, admin_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "trend" in data, f"trend missing: {data.keys()}"
        assert isinstance(data["trend"], list)
        assert len(data["trend"]) == 4, f"expected 4 buckets, got {len(data['trend'])}"
        for b in data["trend"]:
            assert "label" in b and "count" in b
            assert isinstance(b["count"], int)
            assert b["count"] >= 0

    def test_stats_trend_supervisor(self, supervisor_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert len(r.json()["trend"]) == 4

    def test_stats_trend_caseworker_scoped(self, caseworker_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(caseworker_token))
        assert r.status_code == 200
        assert len(r.json()["trend"]) == 4


# ---------------- Beneficiary Reminders ----------------
class TestBeneficiaryReminders:
    def test_reminders_endpoint(self, admin_token):
        r = requests.get(f"{API}/services/beneficiary_reminders/", headers=_h(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0, "expected some overdue beneficiaries"
        row = data[0]
        for k in ("member_id", "name", "household_id", "org_household_number",
                  "service_type", "last_service_date", "days_since"):
            assert k in row, f"missing {k}"
        # tracked service types only
        for row in data:
            assert row["service_type"] in ("HIV Testing Referral", "Individual Counselling")

    def test_reminders_supervisor_ok(self, supervisor_token):
        r = requests.get(f"{API}/services/beneficiary_reminders/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reminders_caseworker_scoped(self, caseworker_token):
        r = requests.get(f"{API}/services/beneficiary_reminders/", headers=_h(caseworker_token))
        assert r.status_code == 200
        # caseworker only sees their scope
        data = r.json()
        assert isinstance(data, list)

    def test_recording_service_removes_from_reminders(self, admin_token):
        # Find a member in reminders
        r = requests.get(f"{API}/services/beneficiary_reminders/", headers=_h(admin_token))
        assert r.status_code == 200
        reminders = r.json()
        if not reminders:
            pytest.skip("no reminders available")
        target = reminders[0]
        member_id = target["member_id"]
        service_type = target["service_type"]
        hh_id = target["household_id"]

        # Record a service
        payload = {
            "household": hh_id,
            "beneficiary_type": "householdmember",
            "beneficiary_id": member_id,
            "service_type": service_type,
            "service_date": str(date.today()),
            "notes": "TEST round7 reminder-clear",
        }
        cr = requests.post(f"{API}/services/", json=payload, headers=_h(admin_token))
        assert cr.status_code in (200, 201), f"create service -> {cr.status_code} {cr.text}"

        # Confirm removed
        r2 = requests.get(f"{API}/services/beneficiary_reminders/", headers=_h(admin_token))
        assert r2.status_code == 200
        after = r2.json()
        still = [x for x in after if x["member_id"] == member_id and x["service_type"] == service_type]
        assert len(still) == 0, f"member+service still in reminders: {still}"


# ---------------- CSV Service Export ----------------
class TestCsvExport:
    EXPECTED_HEADER = ["Date", "Household Number", "Beneficiary", "Service Type", "Delivered By", "Notes"]

    def test_export_admin_200(self, admin_token):
        r = requests.get(f"{API}/services/export/", headers=_h(admin_token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert rows[0] == self.EXPECTED_HEADER

    def test_export_supervisor_200(self, supervisor_token):
        r = requests.get(f"{API}/services/export/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        first = r.text.splitlines()[0]
        assert first == ",".join(self.EXPECTED_HEADER)

    def test_export_caseworker_403(self, caseworker_token):
        r = requests.get(f"{API}/services/export/", headers=_h(caseworker_token))
        assert r.status_code == 403

    def test_export_capturer_403(self, capturer_token):
        r = requests.get(f"{API}/services/export/", headers=_h(capturer_token))
        assert r.status_code == 403

    def test_export_month_query(self, admin_token):
        r = requests.get(f"{API}/services/export/?month=2026-08", headers=_h(admin_token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert "service_report_2026_08" in r.headers.get("Content-Disposition", "")


# ---------------- Race-Safe Household versioning ----------------
class TestRaceSafeVersioning:
    HH_ID = 60

    def _get_hh(self, token):
        r = requests.get(f"{API}/households/{self.HH_ID}/", headers=_h(token))
        assert r.status_code == 200
        return r.json()

    def test_normal_edit_increments_version_by_one(self, admin_token):
        hh = self._get_hh(admin_token)
        v0 = hh["version"]
        payload = {"version": v0, "notes": (hh.get("notes") or "") + "."}
        r = requests.patch(f"{API}/households/{self.HH_ID}/", json=payload, headers=_h(admin_token))
        assert r.status_code == 200, r.text
        hh2 = self._get_hh(admin_token)
        assert hh2["version"] == v0 + 1, f"expected {v0+1}, got {hh2['version']}"

    def test_stale_version_returns_409(self, admin_token):
        hh = self._get_hh(admin_token)
        stale = hh["version"] - 1
        r = requests.patch(f"{API}/households/{self.HH_ID}/",
                           json={"version": stale, "notes": "TEST stale"},
                           headers=_h(admin_token))
        assert r.status_code == 409, f"got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("code") == "version_conflict"
        assert "current_version" in body

    def test_correct_version_after_stale_still_works(self, admin_token):
        hh = self._get_hh(admin_token)
        v0 = hh["version"]
        r = requests.patch(f"{API}/households/{self.HH_ID}/",
                           json={"version": v0, "notes": (hh.get("notes") or "") + "!"},
                           headers=_h(admin_token))
        assert r.status_code == 200
        hh2 = self._get_hh(admin_token)
        assert hh2["version"] == v0 + 1


# ---------------- Round-6 regression ----------------
class TestRound6Regression:
    def test_bulk_log(self, caseworker_token):
        # bulk_log with empty list should be a graceful 200/400 (not 500)
        r = requests.post(f"{API}/services/bulk_log/",
                          json={"household_ids": [], "service_type": "Food Support",
                                "service_date": str(date.today())},
                          headers=_h(caseworker_token))
        assert r.status_code in (200, 201, 400), r.text

    def test_monthly_detail_has_missed(self, supervisor_token):
        r = requests.get(f"{API}/services/monthly_detail/", headers=_h(supervisor_token))
        assert r.status_code == 200
        data = r.json()
        assert "missed" in data
        assert isinstance(data["missed"], list)

    def test_stats_has_staff_org_ranking(self, supervisor_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(supervisor_token))
        assert r.status_code == 200
        d = r.json()
        assert "staff" in d and "org" in d and "ranking" in d

    def test_dashboard_completeness_bands(self, supervisor_token):
        r = requests.get(f"{API}/dashboard/", headers=_h(supervisor_token))
        assert r.status_code == 200
        d = r.json()
        assert "completeness_bands" in d
        for band in ("ready", "in_progress", "needs_attention"):
            assert band in d["completeness_bands"]

    def test_band_filter_households(self, supervisor_token):
        r = requests.get(f"{API}/households/?band=in_progress", headers=_h(supervisor_token))
        assert r.status_code == 200
