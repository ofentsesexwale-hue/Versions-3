from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Caregiver, Household, HouseholdMember, PartnerAgency, PlannedVisit, Referral
from core.sa_id import parse_sa_id


class CaseworkGoldStandardTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user(
            'OrphanCoordinator', password='x', first_name='Orphan', last_name='Coordinator',
            is_staff=True, is_superuser=True,
        )
        self.user.groups.add(Group.objects.get(name='admin'))
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.hh = Household.objects.create(org_household_number='KHAYA-201')
        Caregiver.objects.create(
            household=self.hh, name='Lindiwe', surname='Dlamini',
            id_number='8001015009087',
        )

    def test_parse_sa_id_extracts_dob_and_sex(self):
        parsed = parse_sa_id('8001015009087')
        self.assertTrue(parsed['is_sa_length'])
        self.assertTrue(parsed['luhn_ok'])
        self.assertEqual(parsed['dob'], '1980-01-01')
        self.assertEqual(parsed['sex'], 'Male')

    def test_id_check_flags_duplicate(self):
        other = Household.objects.create(org_household_number='KHAYA-202')
        Caregiver.objects.create(household=other, name='Copy', surname='Dlamini', id_number='8001015009087')
        r = self.client.get('/api/id-check/', {'q': '800101 5009 087'})
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data['duplicates']), 1)

    def test_referral_and_work_diary(self):
        partner = PartnerAgency.objects.create(name='Local SASSA', kind='sassa', is_training=False)
        ref = Referral.objects.create(
            household=self.hh, partner=partner, reason='grant', status='sent',
            follow_up_date=date.today() - timedelta(days=1), created_by=self.user,
        )
        PlannedVisit.objects.create(
            household=self.hh, visit_date=timezone.localdate() - timedelta(days=2),
            visit_type='home', purpose='Grant follow-up', status='planned', created_by=self.user,
        )
        r = self.client.get('/api/work-diary/')
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data['counts']['overdue_visits'], 1)
        self.assertGreaterEqual(r.data['counts']['open_referrals'], 1)
        created = self.client.post('/api/referrals/', {
            'household': self.hh.id, 'reason': 'hiv_test', 'status': 'sent',
            'agency_name': 'Clinic', 'client_name': 'Lindiwe Dlamini',
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['agency_name'], 'Clinic')
        self.assertEqual(ref.household_id, self.hh.id)

    def test_training_user_does_not_see_live_partner(self):
        PartnerAgency.objects.create(name='Live clinic', kind='clinic', is_training=False)
        Group.objects.get_or_create(name='admin')
        demo = User.objects.create_user('admin', password='x')
        demo.groups.add(Group.objects.get(name='admin'))
        tok = Token.objects.create(user=demo)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
        r = c.get('/api/partners/')
        self.assertEqual(r.status_code, 200, r.data)
        payload = r.data.get('results') if isinstance(r.data, dict) else r.data
        names = [p['name'] for p in payload]
        self.assertNotIn('Live clinic', names)

    def test_new_household_gets_generated_file_number(self):
        r = self.client.post('/api/households/', {'town': 'Umlazi'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['org_household_number'], 'SI-0001')
        r2 = self.client.post('/api/households/', {'town': 'Soweto'}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertEqual(r2.data['org_household_number'], 'SI-0002')
        peek = self.client.get('/api/households/next-file-number/')
        self.assertEqual(peek.status_code, 200)
        self.assertEqual(peek.data['org_household_number'], 'SI-0003')

    def test_system_builder_cannot_be_demoted_or_deactivated(self):
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data['is_system_builder'])
        self.assertEqual(me.data['role'], 'admin')

        demote = self.client.patch(
            f'/api/staff/{self.user.pk}/',
            {'role': 'case-worker'},
            format='json',
        )
        self.assertEqual(demote.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)
        self.assertTrue(self.user.groups.filter(name='admin').exists())

        off = self.client.patch(
            f'/api/staff/{self.user.pk}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(off.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

        other = User.objects.create_user(
            'office.lead', password='OfficeLead99',
            is_staff=True, is_superuser=True,
        )
        other.groups.add(Group.objects.get(name='admin'))
        tok = Token.objects.create(user=other)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
        blocked = c.patch(
            f'/api/staff/{self.user.pk}/',
            {'role': 'supervisor'},
            format='json',
        )
        self.assertEqual(blocked.status_code, 400)
        listed = c.get('/api/staff/')
        row = next(u for u in listed.data if u['username'] == 'OrphanCoordinator')
        self.assertTrue(row['is_system_builder'])
        self.assertEqual(row['role'], 'admin')
