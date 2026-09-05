"""Deactivate seeded training classroom logins. Keeps OrphanCoordinator active."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Deactivate TRAINING_USERNAMES. OrphanCoordinator stays active.'

    def handle(self, *args, **options):
        User = get_user_model()
        keep = (getattr(settings, 'SYSTEM_BUILDER_USERNAME', '') or '').lower()
        names = sorted(settings.TRAINING_USERNAMES)
        qs = User.objects.filter(username__in=names)
        if keep:
            qs = qs.exclude(username__iexact=keep)
        updated = qs.update(is_active=False)
        still = (
            User.objects.filter(username__iexact=keep, is_active=True).exists()
            if keep else False
        )
        self.stdout.write(self.style.SUCCESS(
            f'Deactivated {updated} training login(s). '
            f'OrphanCoordinator active={still}.'
        ))
