"""Write a local backup zip of the database and uploaded documents."""
from datetime import datetime
from pathlib import Path
import zipfile

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Zip SQLite (or note Postgres) plus media into backend/backups/."

    def handle(self, *args, **options):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = Path(settings.BASE_DIR) / "backups"
        out_dir.mkdir(exist_ok=True)
        zip_path = out_dir / f"ovc-backup-{stamp}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            db = settings.DATABASES["default"]
            if db["ENGINE"].endswith("sqlite3"):
                db_file = Path(db["NAME"])
                if db_file.exists():
                    zf.write(db_file, arcname=f"db/{db_file.name}")
            media = Path(settings.MEDIA_ROOT)
            if media.exists():
                for path in media.rglob("*"):
                    if path.is_file():
                        zf.write(path, arcname=str(Path("media") / path.relative_to(media)))

        self.stdout.write(self.style.SUCCESS(f"Wrote {zip_path}"))
