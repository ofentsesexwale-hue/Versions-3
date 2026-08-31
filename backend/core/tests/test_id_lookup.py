from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Caregiver, Household, HouseholdMember, digits_only


class IdLookupTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='admin')
        self.user = User.objects.create_user('npo.admin', password='x', first_name='Office', last_name='Admin')
        self.user.groups.add(Group.objects.get(name='admin'))
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.hh = Household.objects.create(org_household_number='KHAYA-104')
        Caregiver.objects.create(
            household=self.hh, name='Thandi', surname='Mokoena',
            id_number='800101 5009 087',
        )
        HouseholdMember.objects.create(
            household=self.hh, name='Sipho', surname='Mokoena',
            id_number='101010-5800-087',
        )

    def test_digits_only_strips_spaces_and_dashes(self):
        self.assertEqual(digits_only('800101 5009 087'), '8001015009087')
        self.assertEqual(digits_only('101010-5800-087'), '1010105800087')

    def test_save_stores_id_number_digits(self):
        self.hh.caregiver.refresh_from_db()
        self.assertEqual(self.hh.caregiver.id_number_digits, '8001015009087')

    def test_lookup_opens_household_from_caregiver_id(self):
        r = self.client.get('/api/households/lookup/', {'q': '8001015009087'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['match'], 'unique')
        self.assertEqual(r.data['households'][0]['id'], self.hh.id)
        self.assertIn('Thandi', r.data['matched_label'])

    def test_lookup_accepts_spaces_in_id(self):
        r = self.client.get('/api/households/lookup/', {'q': '800101 5009 087'})
        self.assertEqual(r.data['match'], 'unique')
        self.assertEqual(r.data['households'][0]['org_household_number'], 'KHAYA-104')

    def test_lookup_opens_from_child_id(self):
        r = self.client.get('/api/households/lookup/', {'q': '1010105800087'})
        self.assertEqual(r.data['match'], 'unique')
        self.assertEqual(r.data['households'][0]['id'], self.hh.id)

    def test_lookup_unknown_id_is_none(self):
        r = self.client.get('/api/households/lookup/', {'q': '9901015800088'})
        self.assertEqual(r.data['match'], 'none')
        self.assertEqual(r.data['households'], [])

    def test_training_user_cannot_see_live_id(self):
        Group.objects.get_or_create(name='admin')
        demo = User.objects.create_user('admin', password='x')
        demo.groups.add(Group.objects.get(name='admin'))
        tok = Token.objects.create(user=demo)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Token {tok.key}')
        r = c.get('/api/households/lookup/', {'q': '8001015009087'})
        self.assertEqual(r.data['match'], 'none')
