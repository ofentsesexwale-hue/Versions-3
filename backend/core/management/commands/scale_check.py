"""Create ~500 live-office people, time the hot APIs, then delete the sample.

Usage:
  python manage.py scale_check
  python manage.py scale_check --people 500 --keep
"""
import io
import time
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Caregiver, CaseFileChecklistItem, Household, HouseholdMember
from core import choices


class Command(BaseCommand):
    help = 'Load-test the live office at organisation scale (~500 people), then clean up.'

    def add_arguments(self, parser):
        parser.add_argument('--people', type=int, default=500)
        parser.add_argument('--keep', action='store_true', help='Leave SCALE- households in the live file.')

    def handle(self, *args, **options):
        target = options['people']
        keep = options['keep']
        prefix = 'SCALE-'
        Household.objects.filter(org_household_number__startswith=prefix).delete()

        admin = User.objects.filter(username='OrphanCoordinator').first() or User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write('No live administrator found.')
            return

        people = 0
        households = 0
        hh_ids = []
        t0 = time.perf_counter()
        while people < target:
            households += 1
            hh = Household.objects.create(
                org_household_number=f'{prefix}{households:04d}',
                town='Umlazi',
                province='KwaZulu-Natal',
                date_registered=date.today() - timedelta(days=households % 400),
            )
            CaseFileChecklistItem.objects.bulk_create([
                CaseFileChecklistItem(household=hh, category=cat, sub_item=sub)
                for cat, sub in choices.CHECKLIST_TEMPLATE
            ])
            Caregiver.objects.create(
                household=hh,
                name='Live',
                surname=f'Family{households}',
                id_number=f'8{households:012d}'[:13],
                surname_confirmed=True,
                id_number_confirmed=True,
            )
            people += 1
            kids = min(3, max(1, target - people))
            if people + kids > target:
                kids = max(0, target - people)
            members = [
                HouseholdMember(
                    household=hh,
                    name=f'Child{j}',
                    surname=f'Family{households}',
                    relationship_to_head='Child',
                    id_number=f'0{households:04d}{j:08d}'[:13],
                    surname_confirmed=True,
                    id_number_confirmed=True,
                )
                for j in range(kids)
            ]
            HouseholdMember.objects.bulk_create(members)
            people += kids
            hh_ids.append(hh.id)

        create_s = time.perf_counter() - t0
        self.stdout.write(f'Created {households} households / {people} people in {create_s:.2f}s')

        buf = io.BytesIO()
        Image.new("RGB", (24, 24), (40, 90, 50)).save(buf, format="PNG")
        png_bytes = buf.getvalue()
        pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF\n"
        token, _ = Token.objects.get_or_create(user=admin)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        uploaded = 0
        t1 = time.perf_counter()
        sample_hhs = Household.objects.filter(id__in=hh_ids[:40]).prefetch_related('members', 'caregiver')
        for hh in sample_hhs:
            people_on = []
            if getattr(hh, 'caregiver', None):
                people_on.append(('caregiver', hh.caregiver.id))
            for m in hh.members.all()[:2]:
                people_on.append(('householdmember', m.id))
            for kind, pid in people_on:
                for name, body, ctype in (
                    ('id.png', png_bytes, 'image/png'),
                    ('clinic.pdf', pdf_bytes, 'application/pdf'),
                ):
                    resp = client.post(
                        '/api/documents/',
                        {
                            'parent_type': kind,
                            'parent_id': pid,
                            'category': 'vital_document',
                            'label': name,
                            'file': SimpleUploadedFile(name, body, content_type=ctype),
                        },
                        format='multipart',
                    )
                    if resp.status_code in (200, 201):
                        uploaded += 1
                    elif uploaded == 0:
                        self.stderr.write(f'First upload failed {resp.status_code}: {resp.data}')
        upload_s = time.perf_counter() - t1
        self.stdout.write(f'Uploaded {uploaded} PNG/PDF files in {upload_s:.2f}s')

        def timed(label, path):
            start = time.perf_counter()
            resp = client.get(path)
            ms = (time.perf_counter() - start) * 1000
            ok = resp.status_code == 200
            self.stdout.write(f'  {label}: {resp.status_code} in {ms:.0f}ms')
            return ok, ms

        self.stdout.write('Hot paths as OrphanCoordinator:')
        results = [
            timed('dashboard', '/api/dashboard/'),
            timed('household list', '/api/households/?page_size=50'),
            timed('search', '/api/households/?q=Family10'),
            timed('documents', f'/api/documents/?household={hh_ids[0]}&page_size=100'),
        ]
        dash = client.get('/api/dashboard/').data
        self.stdout.write(
            f'Live stats during test: households={dash["stats"]["total_households"]} '
            f'people={dash["stats"].get("total_people")} docs={dash["stats"].get("document_count")}'
        )

        slow = [ms for ok, ms in results if ms > 2000]
        if slow:
            self.stderr.write(self.style.WARNING(f'{len(slow)} endpoints took over 2s — review indexes.'))
        else:
            self.stdout.write(self.style.SUCCESS('All hot paths under 2s at ~500 people.'))

        if not keep:
            n, _ = Household.objects.filter(org_household_number__startswith=prefix).delete()
            self.stdout.write(f'Removed scale-test rows ({n} objects). Live office is empty again.')
        else:
            self.stdout.write(self.style.WARNING('Kept SCALE- households in the live office.'))
