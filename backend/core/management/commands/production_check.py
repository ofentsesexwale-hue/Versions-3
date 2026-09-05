"""Office go-live checks. Does not delete SI- households or any data."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.backup_ops import backup_dir


class Command(BaseCommand):
    help = (
        'PASS/FAIL checks for production: DEBUG, secret key, training users, '
        'MEDIA_ROOT writable, backup folder present. Never deletes SI- households.'
    )

    def handle(self, *args, **options):
        rows = []
        failed = False

        def check(label, ok, detail):
            nonlocal failed
            status = 'PASS' if ok else 'FAIL'
            if not ok:
                failed = True
            rows.append((status, label, detail))

        check(
            'DJANGO_DEBUG is False',
            not settings.DEBUG,
            f'DEBUG={settings.DEBUG}',
        )

        insecure = getattr(
            settings,
            'INSECURE_DEFAULT_SECRET_KEY',
            'insecure-local-dev-key-change-me',
        )
        secret = settings.SECRET_KEY or ''
        check(
            'DJANGO_SECRET_KEY is set (not the insecure default)',
            bool(secret) and secret != insecure,
            'Set DJANGO_SECRET_KEY in backend/.env',
        )

        User = get_user_model()
        active_training = list(
            User.objects.filter(
                username__in=settings.TRAINING_USERNAMES,
                is_active=True,
            ).values_list('username', flat=True)
        )
        check(
            'Training users are deactivated',
            len(active_training) == 0,
            (
                'All training logins inactive'
                if not active_training
                else f'Still active: {", ".join(sorted(active_training))} — run disable_training_users'
            ),
        )

        media = Path(settings.MEDIA_ROOT)
        writable = False
        detail = str(media)
        try:
            media.mkdir(parents=True, exist_ok=True)
            probe = media / '.ovc-write-probe'
            probe.write_text('ok', encoding='utf-8')
            probe.unlink(missing_ok=True)
            writable = True
            detail = f'{media} is writable'
        except OSError as exc:
            detail = f'{media} not writable: {exc}'
        check('MEDIA_ROOT is writable', writable, detail)

        bdir = backup_dir()
        check(
            'Backup folder present',
            bdir.is_dir(),
            str(bdir),
        )

        for status, label, detail in rows:
            style = self.style.SUCCESS if status == 'PASS' else self.style.ERROR
            self.stdout.write(style(f'{status}  {label} — {detail}'))

        self.stdout.write('Note: This command never deletes SI- households or case files.')
        if failed:
            raise CommandError('production_check failed. Fix FAIL items before going live.')
        self.stdout.write(self.style.SUCCESS('All production checks passed.'))
