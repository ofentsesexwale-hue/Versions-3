"""Seed groups, demo users, and fictional (AI-generated) test data.

ALL data produced here is fictional. No real beneficiary information is used.
Household numbers are prefixed with "TEST" to make this unmistakable.
"""
import random
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from core import choices
from core.models import (
    Caregiver,
    CaseFileChecklistItem,
    Household,
    HouseholdMember,
    PartnerAgency,
    PlannedVisit,
    Referral,
)

fake = Faker('en_US')

DEMO_USERS = [
    ('admin', 'admin123', 'admin', 'Amina', 'Ndlovu', True),
    ('supervisor', 'supervisor123', 'supervisor', 'Sipho', 'Khumalo', False),
    ('caseworker', 'caseworker123', 'case-worker', 'Cindy', 'Mokoena', False),
    ('caseworker2', 'caseworker123', 'case-worker', 'Thabo', 'Zulu', False),
    ('capturer', 'capturer123', 'data-capturer', 'Cathy', 'Dlamini', False),
]

LIVE_ADMIN_USERNAME = 'OrphanCoordinator'
LIVE_ADMIN_PASSWORD = 'Khaya-File-7nQ2'

SA_SURNAMES = ['Nkosi', 'Dlamini', 'Mokoena', 'Khumalo', 'Ndlovu', 'Zulu', 'Sithole',
               'Mthembu', 'Mahlangu', 'Botha', 'Van der Merwe', 'Naidoo', 'Pillay',
               'Adams', 'Jacobs', 'Molefe', 'Radebe', 'Mabaso', 'Tshabalala', 'Cele']
PROVINCES = ['KwaZulu-Natal', 'Gauteng', 'Eastern Cape', 'Limpopo', 'Mpumalanga',
             'Western Cape', 'North West', 'Free State', 'Northern Cape']
TOWNS = ['Umlazi', 'Soweto', 'Mthatha', 'Polokwane', 'Nelspruit', 'Khayelitsha',
         'Mahikeng', 'Bloemfontein', 'Kimberley', 'Pietermaritzburg']
LANGUAGES = ['isiZulu', 'isiXhosa', 'Sepedi', 'Setswana', 'English', 'Afrikaans', 'Sesotho']
RELATIONSHIPS = ['Son', 'Daughter', 'Grandchild', 'Niece', 'Nephew', 'Foster child', 'Sibling']


def luhn_check_digit(number_str):
    digits = [int(d) for d in number_str]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
    return (10 - (total % 10)) % 10


def sa_id_number(dob, sex):
    yy = dob.strftime('%y')
    mm = dob.strftime('%m')
    dd = dob.strftime('%d')
    seq = random.randint(5000, 9999) if sex == 'Male' else random.randint(0, 4999)
    seq_str = f'{seq:04d}'
    citizen = '0'
    a = '8'
    partial = f'{yy}{mm}{dd}{seq_str}{citizen}{a}'
    check = luhn_check_digit(partial)
    return f'{partial}{check}'


class Command(BaseCommand):
    help = 'Seed groups, demo users, and fictional test data.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Wipe existing households and reseed.')
        parser.add_argument('--count', type=int, default=60)

    def handle(self, *args, **options):
        self.stdout.write('Creating groups...')
        for role in choices_all_roles():
            Group.objects.get_or_create(name=role)

        self.stdout.write('Creating demo users...')
        users_by_role = {}
        for username, password, role, first, last, is_super in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last,
                          'is_staff': is_super, 'is_superuser': is_super},
            )
            user.first_name = first
            user.last_name = last
            user.is_staff = is_super
            user.is_superuser = is_super
            user.is_active = True
            user.set_password(password)
            user.save()
            user.groups.clear()
            user.groups.add(Group.objects.get(name=role))
            users_by_role[role] = user
            self.stdout.write(f'  {username} / {password}  ({role})')

        self._ensure_live_admin()

        admin_user = User.objects.get(username='admin')
        caseworker = User.objects.get(username='caseworker')

        if options['force']:
            self.stdout.write('Wiping training (TEST-) households only...')
            Household.objects.filter(org_household_number__istartswith='TEST').delete()

        if Household.objects.filter(org_household_number__istartswith='TEST').exists():
            self.stdout.write(self.style.WARNING(
                'Training households already exist; skipping data seed. Use --force to reseed TEST- files only.'))
            self._ensure_training_assignments(caseworker)
            self._ensure_training_casework(admin_user, caseworker)
            self.stdout.write(self.style.SUCCESS('Done.'))
            return

        count = options['count']
        self.stdout.write(f'Creating {count} fictional households...')
        cat_keys = [c[0] for c in choices.CATEGORY_CHOICES]

        for i in range(1, count + 1):
            surname = random.choice(SA_SURNAMES)
            hh = Household.objects.create(
                org_household_number=f'TEST-{i:04d}',
                house_number=str(random.randint(1, 250)),
                street=fake.street_name(),
                town=random.choice(TOWNS),
                province=random.choice(PROVINCES),
                district=f'{random.choice(TOWNS)} District',
                municipality=f'{random.choice(TOWNS)} Local Municipality',
                ward=f'Ward {random.randint(1, 40)}',
                date_registered=date.today() - timedelta(days=random.randint(0, 900)),
            )

            # Caregiver (Head of Household)
            cg_sex = random.choice(['Male', 'Female'])
            cg_dob = fake.date_between(start_date='-70y', end_date='-25y')
            cg = Caregiver(
                household=hh,
                id_type='SA ID Number',
                id_number=sa_id_number(cg_dob, cg_sex),
                name=fake.first_name_male() if cg_sex == 'Male' else fake.first_name_female(),
                surname=surname,
                known_as='',
                nationality='South African',
                date_of_birth=cg_dob,
                sex=cg_sex,
                race=random.choice(['African', 'African', 'African', 'Coloured', 'White', 'Indian']),
                marital_status=random.choice([c[0] for c in choices.MARITAL_STATUS_CHOICES]),
                disability=random.random() < 0.08,
                cell_number=f'0{random.randint(60, 84)}{random.randint(1000000, 9999999)}',
                home_language=random.choice(LANGUAGES),
                headship_type=random.choice([c[0] for c in choices.HEADSHIP_TYPE_CHOICES]),
                date_joined=hh.date_registered,
            )
            self._apply_confirm_flags(cg, admin_user)
            cg.save()

            # Members (children)
            for _ in range(random.randint(1, 4)):
                m_sex = random.choice(['Male', 'Female'])
                m_dob = fake.date_between(start_date='-18y', end_date='-1y')
                mem = HouseholdMember(
                    household=hh,
                    id_type=random.choice(['SA ID Number', 'SA ID Number', 'Passport Number']),
                    id_number=sa_id_number(m_dob, m_sex),
                    name=fake.first_name_male() if m_sex == 'Male' else fake.first_name_female(),
                    surname=surname,
                    nationality='South African',
                    date_of_birth=m_dob,
                    sex=m_sex,
                    race=cg.race,
                    disability=random.random() < 0.06,
                    relationship_to_head=random.choice(RELATIONSHIPS),
                    date_joined=hh.date_registered,
                )
                self._apply_confirm_flags(mem, admin_user)
                mem.save()

            # Checklist rows
            for cat_key, sub_item in choices.CHECKLIST_TEMPLATE:
                has = random.choice(['Yes', 'Yes', 'No', ''])
                CaseFileChecklistItem.objects.create(
                    household=hh,
                    category=cat_key,
                    sub_item=sub_item,
                    has_evidence=has,
                )

            # Assign training files to demo case-workers (not live staff).
            if random.random() < 0.55:
                hh.assigned_to.add(caseworker)
            elif 'caseworker2' in {u.username for u in User.objects.filter(username='caseworker2')}:
                cw2 = User.objects.filter(username='caseworker2').first()
                if cw2:
                    hh.assigned_to.add(cw2)

        cw2 = User.objects.filter(username='caseworker2').first()
        extra = cw2.assigned_households.count() if cw2 else 0
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {count} training households. "{caseworker.username}" has '
            f'{caseworker.assigned_households.count()} assigned'
            + (f'; caseworker2 has {extra}.' if cw2 else '.')))
        self._ensure_training_casework(admin_user, caseworker)

    def _ensure_live_admin(self):
        """Live office administrator — not a training classroom login."""
        admin_group = Group.objects.get(name='admin')
        old = User.objects.filter(username='npo.admin').first()
        live = User.objects.filter(username=LIVE_ADMIN_USERNAME).first()
        if old and not live:
            old.username = LIVE_ADMIN_USERNAME
            live = old
        if not live:
            live = User(username=LIVE_ADMIN_USERNAME)
        live.first_name = 'Orphan'
        live.last_name = 'Coordinator'
        live.is_staff = True
        live.is_superuser = True
        live.is_active = True
        live.set_password(LIVE_ADMIN_PASSWORD)
        live.save()
        live.groups.add(admin_group)
        if old and old.pk != live.pk:
            old.is_active = False
            old.save(update_fields=['is_active'])
        self.stdout.write(f'  {LIVE_ADMIN_USERNAME}  (live administrator)')

    def _apply_confirm_flags(self, person, admin_user):
        now = timezone.now()
        for field in ['surname', 'id_number', 'date_of_birth']:
            confirmed = random.random() < 0.6
            setattr(person, f'{field}_confirmed', confirmed)
            if confirmed:
                setattr(person, f'{field}_confirmed_by', admin_user)
                setattr(person, f'{field}_confirmed_at', now)

    def _ensure_training_assignments(self, caseworker):
        cw2 = User.objects.filter(username='caseworker2').first()
        qs = Household.objects.filter(org_household_number__istartswith='TEST')
        for i, hh in enumerate(qs):
            if hh.assigned_to.exists():
                continue
            hh.assigned_to.add(caseworker if i % 2 == 0 else (cw2 or caseworker))

    def _ensure_training_casework(self, admin_user, caseworker):
        """Sample partners, referrals and visits for training — never live office."""
        if not PartnerAgency.objects.filter(is_training=True).exists():
            PartnerAgency.objects.bulk_create([
                PartnerAgency(name='Umlazi SASSA office', kind='sassa', phone='031 000 0000',
                              address='Mangosuthu Highway', is_training=True),
                PartnerAgency(name='Prince Mshiyeni clinic', kind='clinic', phone='031 000 1111',
                              address='Umlazi', is_training=True),
                PartnerAgency(name='SAPS Umlazi', kind='police', phone='10111', is_training=True),
                PartnerAgency(name='Home Affairs Durban', kind='home_affairs', is_training=True),
            ])
        hh = Household.objects.filter(org_household_number='TEST-0001').first()
        if not hh:
            return
        partner = PartnerAgency.objects.filter(is_training=True, kind='sassa').first()
        if not Referral.objects.filter(household=hh).exists():
            Referral.objects.create(
                household=hh, partner=partner, reason='grant',
                client_name='Joseph Adams', details='Apply for CSG',
                status='sent', follow_up_date=timezone.localdate() - timedelta(days=2),
                created_by=admin_user,
            )
        if not PlannedVisit.objects.filter(household=hh).exists():
            PlannedVisit.objects.create(
                household=hh, visit_date=timezone.localdate() - timedelta(days=3),
                visit_type='home', purpose='Follow up on grant application',
                status='planned', assigned_to=caseworker, created_by=admin_user,
            )
            PlannedVisit.objects.create(
                household=hh, visit_date=timezone.localdate() + timedelta(days=2),
                visit_type='school', purpose='Teacher feedback',
                status='planned', assigned_to=caseworker, created_by=admin_user,
            )


def choices_all_roles():
    from django.conf import settings
    return settings.ALL_ROLES
