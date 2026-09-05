"""Write a local backup zip of the database and uploaded documents."""
from django.core.management.base import BaseCommand

from core.backup_ops import create_backup_zip


class Command(BaseCommand):
    help = (
        'Zip db.sqlite3 plus the full MEDIA_ROOT (case-files, vital-documents, '
        'documents, scan_intake) into backend/backups/ovc-backup-YYYYMMDD-HHMMSS.zip.'
    )

    def handle(self, *args, **options):
        zip_path = create_backup_zip()
        self.stdout.write(self.style.SUCCESS(f'Wrote {zip_path}'))
