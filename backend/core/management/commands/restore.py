"""Restore SQLite + MEDIA_ROOT from an ovc-backup-*.zip. Requires --force to overwrite."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.backup_ops import backup_dir, restore_from_zip


class Command(BaseCommand):
    help = (
        'Restore db.sqlite3 and MEDIA_ROOT from a backup zip. '
        'Refuses to overwrite live files unless --force is passed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'zip_path',
            nargs='?',
            help='Path to ovc-backup-*.zip (default: newest in backend/backups/)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite the live database and MEDIA_ROOT on this PC.',
        )

    def handle(self, *args, **options):
        zip_arg = options.get('zip_path')
        if zip_arg:
            zip_path = Path(zip_arg)
        else:
            zips = sorted(backup_dir().glob('ovc-backup-*.zip'), reverse=True)
            if not zips:
                raise CommandError('No ovc-backup-*.zip found in backend/backups/.')
            zip_path = zips[0]
        if not zip_path.is_file():
            raise CommandError(f'Backup not found: {zip_path}')
        try:
            restored = restore_from_zip(zip_path, force=bool(options.get('force')))
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Restored from {zip_path.name} → {restored}. Restart the app.'
        ))
