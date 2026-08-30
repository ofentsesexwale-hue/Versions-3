"""Round-8 tests: DOB Prompt, Service Targets, CSV Column Picker + regression."""
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


def _h(t):
    return {"Authorization": f"Token {t}"}


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


# ---------------- DOB Prompt ----------------
class TestDobPrompt:
    def test_missing_dob_admin(self, admin_token):
        r = requests.get(f"{API}/members/missing_dob/", headers=_h(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)

    def test_missing_dob_supervisor(self, supervisor_token):
        r = requests.get(f"{API}/members/missing_dob/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_missing_dob_caseworker_scoped(self, caseworker_token):
        r = requests.get(f"{API}/members/missing_dob/", headers=_h(caseworker_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_null_dob_then_returned_then_restore(self, admin_token):
        # Find a member with a DOB
        r = requests.get(f"{API}/members/", headers=_h(admin_token))
        assert r.status_code == 200
        members = r.json()
        if isinstance(members, dict) and "results" in members:
            members = members["results"]
        target = next((m for m in members if m.get("date_of_birth")), None)
        if not target:
            pytest.skip("no member with a DOB available")
        member_id = target["id"]
        orig_dob = target["date_of_birth"]

        # Null the DOB
        pr = requests.patch(f"{API}/members/{member_id}/",
                            json={"date_of_birth": None}, headers=_h(admin_token))
        assert pr.status_code in (200, 202), pr.text

        # It should now show up in missing_dob
        mr = requests.get(f"{API}/members/missing_dob/", headers=_h(admin_token))
        assert mr.status_code == 200
        rows = mr.json()
        found = [x for x in rows if x["id"] == member_id]
        assert len(found) == 1, f"member {member_id} not in missing_dob"
        row = found[0]
        for k in ("id", "name", "household_id", "org_household_number"):
            assert k in row, f"missing key {k}"

        # Restore
        rr = requests.patch(f"{API}/members/{member_id}/",
                            json={"date_of_birth": orig_dob}, headers=_h(admin_token))
        assert rr.status_code in (200, 202), rr.text

        # Confirm gone
        mr2 = requests.get(f"{API}/members/missing_dob/", headers=_h(admin_token))
        after = [x for x in mr2.json() if x["id"] == member_id]
        assert len(after) == 0, "member still in missing_dob after restore"


# ---------------- Service Targets ----------------
class TestServiceTargets:
    def test_targets_list_admin(self, admin_token):
        r = requests.get(f"{API}/service-targets/", headers=_h(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for row in data:
            for k in ("user_id", "name", "username", "monthly_goal"):
                assert k in row

    def test_targets_list_supervisor(self, supervisor_token):
        r = requests.get(f"{API}/service-targets/", headers=_h(supervisor_token))
        assert r.status_code == 200

    def test_targets_caseworker_403(self, caseworker_token):
        r = requests.get(f"{API}/service-targets/", headers=_h(caseworker_token))
        assert r.status_code == 403

    def test_targets_capturer_403(self, capturer_token):
        r = requests.get(f"{API}/service-targets/", headers=_h(capturer_token))
        assert r.status_code == 403

    def test_targets_put_supervisor_upsert(self, supervisor_token):
        # Get a worker id
        r = requests.get(f"{API}/service-targets/", headers=_h(supervisor_token))
        assert r.status_code == 200
        workers = r.json()
        assert workers
        uid = workers[0]["user_id"]
        orig = workers[0]["monthly_goal"]

        # Set goal
        pr = requests.put(f"{API}/service-targets/",
                          json={"user_id": uid, "monthly_goal": 20},
                          headers=_h(supervisor_token))
        assert pr.status_code == 200, pr.text
        body = pr.json()
        assert body["user_id"] == uid
        assert body["monthly_goal"] == 20

        # Verify persisted
        r2 = requests.get(f"{API}/service-targets/", headers=_h(supervisor_token))
        found = next(w for w in r2.json() if w["user_id"] == uid)
        assert found["monthly_goal"] == 20

        # Restore
        requests.put(f"{API}/service-targets/",
                     json={"user_id": uid, "monthly_goal": orig},
                     headers=_h(supervisor_token))

    def test_targets_put_caseworker_403(self, caseworker_token):
        r = requests.put(f"{API}/service-targets/",
                         json={"user_id": 1, "monthly_goal": 5},
                         headers=_h(caseworker_token))
        assert r.status_code == 403

    def test_stats_ranking_has_goal_fields(self, admin_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(admin_token))
        assert r.status_code == 200
        d = r.json()
        assert "ranking" in d
        assert isinstance(d["ranking"], list)
        for row in d["ranking"]:
            for k in ("delivered", "goal", "goal_percent"):
                assert k in row, f"ranking row missing {k}: {row}"

    def test_stats_caseworker_staff_goal(self, caseworker_token):
        # caseworker (user 3) has goal=15 per pre-req; delivered=23 -> percent=153
        r = requests.get(f"{API}/services/stats/", headers=_h(caseworker_token))
        assert r.status_code == 200
        d = r.json()
        assert "staff" in d
        # staff dict should carry a goal/goal_percent for a worker with a target set
        assert "goal" in d["staff"]
        assert "goal_percent" in d["staff"]


# ---------------- CSV Column Picker ----------------
class TestCsvColumnPicker:
    ALL_HEADER = ["Date", "Household Number", "Beneficiary", "Service Type", "Delivered By", "Notes"]

    def test_no_columns_returns_all(self, admin_token):
        r = requests.get(f"{API}/services/export/", headers=_h(admin_token))
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == self.ALL_HEADER

    def test_columns_subset(self, admin_token):
        r = requests.get(f"{API}/services/export/?columns=date,service_type",
                         headers=_h(admin_token))
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == ["Date", "Service Type"]
        # each data row has exactly 2 cols
        for row in rows[1:]:
            assert len(row) == 2

    def test_columns_reordered_but_returned_in_canonical_order(self, admin_token):
        # Requested order may or may not be preserved; at minimum only-valid subset returned
        r = requests.get(f"{API}/services/export/?columns=notes,date",
                         headers=_h(admin_token))
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert set(rows[0]) == {"Date", "Notes"}

    def test_invalid_columns_fallback_all(self, admin_token):
        r = requests.get(f"{API}/services/export/?columns=foo,bar",
                         headers=_h(admin_token))
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == self.ALL_HEADER

    def test_empty_columns_fallback_all(self, admin_token):
        r = requests.get(f"{API}/services/export/?columns=",
                         headers=_h(admin_token))
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == self.ALL_HEADER

    def test_caseworker_403(self, caseworker_token):
        r = requests.get(f"{API}/services/export/?columns=date",
                         headers=_h(caseworker_token))
        assert r.status_code == 403

    def test_capturer_403(self, capturer_token):
        r = requests.get(f"{API}/services/export/?columns=date",
                         headers=_h(capturer_token))
        assert r.status_code == 403


# ---------------- Regression ----------------
class TestRegression:
    def test_trend_4_buckets(self, supervisor_token):
        r = requests.get(f"{API}/services/stats/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert len(r.json()["trend"]) == 4

    def test_beneficiary_reminders(self, admin_token):
        r = requests.get(f"{API}/services/beneficiary_reminders/", headers=_h(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_monthly_detail_missed(self, supervisor_token):
        r = requests.get(f"{API}/services/monthly_detail/", headers=_h(supervisor_token))
        assert r.status_code == 200
        assert "missed" in r.json()

    def test_bulk_log_empty(self, caseworker_token):
        r = requests.post(f"{API}/services/bulk_log/",
                          json={"household_ids": [], "service_type": "Food Support",
                                "service_date": str(date.today())},
                          headers=_h(caseworker_token))
        assert r.status_code in (200, 201, 400)

    def test_completeness_bands(self, supervisor_token):
        r = requests.get(f"{API}/dashboard/", headers=_h(supervisor_token))
        assert r.status_code == 200
        d = r.json()
        assert "completeness_bands" in d
        for b in ("ready", "in_progress", "needs_attention"):
            assert b in d["completeness_bands"]

    def test_band_filter(self, supervisor_token):
        r = requests.get(f"{API}/households/?band=in_progress", headers=_h(supervisor_token))
        assert r.status_code == 200

    def test_version_lock_stale_409(self, admin_token):
        HH = 60
        r = requests.get(f"{API}/households/{HH}/", headers=_h(admin_token))
        assert r.status_code == 200
        v = r.json()["version"]
        pr = requests.patch(f"{API}/households/{HH}/",
                            json={"version": v - 1, "notes": "TEST stale round8"},
                            headers=_h(admin_token))
        assert pr.status_code == 409
        assert pr.json().get("code") == "version_conflict"

    def test_version_lock_correct_200(self, admin_token):
        HH = 60
        r = requests.get(f"{API}/households/{HH}/", headers=_h(admin_token))
        v = r.json()["version"]
        notes = r.json().get("notes") or ""
        pr = requests.patch(f"{API}/households/{HH}/",
                            json={"version": v, "notes": notes + "."},
                            headers=_h(admin_token))
        assert pr.status_code == 200
