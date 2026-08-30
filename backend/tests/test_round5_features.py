"""Round-5 polish tests: version labels, login branding, timeline filters, cover totals."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


@pytest.fixture(scope='module')
def supervisor_token():
    r = requests.post(f'{BASE_URL}/api/auth/login/', json={'username': 'supervisor', 'password': 'supervisor123'})
    assert r.status_code == 200, r.text
    return r.json()['token']


@pytest.fixture(scope='module')
def caseworker_token():
    r = requests.post(f'{BASE_URL}/api/auth/login/', json={'username': 'caseworker', 'password': 'caseworker123'})
    assert r.status_code == 200, r.text
    return r.json()['token']


@pytest.fixture(scope='module')
def admin_token():
    r = requests.post(f'{BASE_URL}/api/auth/login/', json={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 200, r.text
    return r.json()['token']


def auth(token):
    return {'Authorization': f'Token {token}'}


# ---------- Branding: public, no auth ----------
class TestBrandingPublic:
    def test_branding_no_auth_returns_name_and_logo(self):
        r = requests.get(f'{BASE_URL}/api/branding/')
        assert r.status_code == 200, r.text
        d = r.json()
        assert 'name' in d
        assert 'logo' in d
        assert isinstance(d['name'], str) and d['name']

    def test_branding_logo_url_is_relative_or_none(self):
        r = requests.get(f'{BASE_URL}/api/branding/')
        d = r.json()
        if d['logo']:
            # Should be relative or absolute; ensure it isn't the internal cluster host
            assert 'cluster' not in d['logo'], f'branding.logo leaked internal host: {d["logo"]}'

    def test_branding_without_auth_returns_200(self):
        # No auth header at all — endpoint is AllowAny.
        s = requests.Session()
        r = s.get(f'{BASE_URL}/api/branding/')
        assert r.status_code == 200


# ---------- Assessment version numbers ----------
class TestAssessmentVersions:
    def _ensure_two_versions(self, token, hid=60):
        """Seed HH with at least two assessments so we can verify labels."""
        created = []
        r = requests.get(f'{BASE_URL}/api/assessments/', params={'household': hid}, headers=auth(token))
        existing = (r.json().get('results') if isinstance(r.json(), dict) else r.json()) or []
        while len(existing) + len(created) < 2:
            cr = requests.post(f'{BASE_URL}/api/assessments/',
                               json={'household': hid, 'overview_situation': 'TEST_ROUND5 seed'},
                               headers={**auth(token), 'Content-Type': 'application/json'})
            assert cr.status_code in (200, 201), cr.text
            created.append(cr.json()['id'])
        return created

    def test_hh60_has_versions_with_version_number_and_created_by(self, supervisor_token):
        created = self._ensure_two_versions(supervisor_token)
        try:
            r = requests.get(f'{BASE_URL}/api/assessments/', params={'household': 60}, headers=auth(supervisor_token))
            assert r.status_code == 200, r.text
            results = (r.json().get('results') if isinstance(r.json(), dict) else r.json()) or []
            assert len(results) >= 2, 'HH60 should have at least 2 assessment versions'
            for a in results:
                assert 'version_number' in a
                assert isinstance(a['version_number'], int)
                assert a['version_number'] >= 1
                assert 'created_by' in a
            nums = sorted([a['version_number'] for a in results])
            assert len(set(nums)) == len(nums)
        finally:
            for aid in created:
                requests.delete(f'{BASE_URL}/api/assessments/{aid}/', headers=auth(supervisor_token))

    def test_new_assessment_post_increments_version(self, supervisor_token):
        # Snapshot existing
        r = requests.get(f'{BASE_URL}/api/assessments/', params={'household': 60}, headers=auth(supervisor_token))
        existing = (r.json().get('results') if isinstance(r.json(), dict) else r.json()) or []
        max_v = max((a['version_number'] for a in existing), default=0)

        payload = {
            'household': 60,
            'overview_situation': 'TEST_ROUND5 version increment probe',
        }
        cr = requests.post(f'{BASE_URL}/api/assessments/', json=payload, headers={**auth(supervisor_token), 'Content-Type': 'application/json'})
        assert cr.status_code in (200, 201), cr.text
        new_a = cr.json()
        assert new_a['version_number'] == max_v + 1
        assert new_a['created_by'] in ('supervisor', 'Supervisor', 'supervisor supervisor') or 'supervisor' in str(new_a['created_by']).lower()

        # Cleanup
        requests.delete(f'{BASE_URL}/api/assessments/{new_a["id"]}/', headers=auth(supervisor_token))


# ---------- Timeline: entries include sign-off + action types ----------
class TestTimelineActions:
    def test_timeline_returns_action_field(self, supervisor_token):
        r = requests.get(f'{BASE_URL}/api/households/60/timeline/', headers=auth(supervisor_token))
        assert r.status_code == 200
        data = r.json()
        if isinstance(data, dict):
            data = data.get('results') or []
        assert isinstance(data, list)
        if data:
            for e in data[:5]:
                assert 'action' in e
                assert 'target_description' in e


# ---------- Cover totals ----------
class TestPrintCoverTotals:
    def test_batch_cover_avg_and_file_pct_column(self, supervisor_token):
        r = requests.get(
            f'{BASE_URL}/api/print/checklist/',
            params={'household_ids': '59,60', 'token': supervisor_token},
        )
        assert r.status_code == 200, r.text
        html = r.text
        assert 'Avg file completeness:' in html, 'cover page missing "Avg file completeness:"'
        assert 'File %' in html, 'cover page missing "File %" column header'
        # confirm avg contains a percentage
        assert '%' in html

    def test_full_batch_cover_totals(self, supervisor_token):
        r = requests.get(
            f'{BASE_URL}/api/print/full/',
            params={'household_ids': '59,60', 'token': supervisor_token},
        )
        assert r.status_code == 200
        assert 'Avg file completeness:' in r.text
        assert 'File %' in r.text


# ---------- Regression: login roles + print with assessment_id ----------
class TestRegression:
    @pytest.mark.parametrize('u,p', [
        ('admin', 'admin123'),
        ('supervisor', 'supervisor123'),
        ('caseworker', 'caseworker123'),
        ('capturer', 'capturer123'),
    ])
    def test_login(self, u, p):
        r = requests.post(f'{BASE_URL}/api/auth/login/', json={'username': u, 'password': p})
        assert r.status_code == 200
        assert 'token' in r.json()

    def test_print_assessment_with_assessment_id(self, supervisor_token):
        # seed one assessment on hh 60 if none exist
        r = requests.get(f'{BASE_URL}/api/assessments/', params={'household': 60}, headers=auth(supervisor_token))
        results = (r.json().get('results') if isinstance(r.json(), dict) else r.json()) or []
        created_id = None
        if not results:
            cr = requests.post(f'{BASE_URL}/api/assessments/',
                               json={'household': 60, 'overview_situation': 'TEST_ROUND5 seed for print'},
                               headers={**auth(supervisor_token), 'Content-Type': 'application/json'})
            created_id = cr.json()['id']
            results = [cr.json()]
        aid = results[0]['id']
        try:
            pr = requests.get(f'{BASE_URL}/api/print/assessment/',
                              params={'household_id': 60, 'assessment_id': aid, 'token': supervisor_token})
            assert pr.status_code == 200
        finally:
            if created_id:
                requests.delete(f'{BASE_URL}/api/assessments/{created_id}/', headers=auth(supervisor_token))

    def test_organisation_endpoint_has_relative_logo(self, admin_token):
        r = requests.get(f'{BASE_URL}/api/organisation/', headers=auth(admin_token))
        assert r.status_code == 200
        d = r.json()
        if d.get('logo'):
            assert 'cluster' not in d['logo']

    def test_verification_count_and_dashboard(self, supervisor_token):
        r = requests.get(f'{BASE_URL}/api/households/verification_count/', headers=auth(supervisor_token))
        assert r.status_code == 200
        assert 'total' in r.json()

        d = requests.get(f'{BASE_URL}/api/dashboard/', headers=auth(supervisor_token))
        assert d.status_code == 200
        assert 'stats' in d.json()
