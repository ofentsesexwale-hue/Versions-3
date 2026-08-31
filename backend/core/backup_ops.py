"""Local zip backup / restore of SQLite and uploaded files. No cloud."""
from datetime import datetime
from pathlib import Path
import shutil
import tempfile
import zipfile

from django.conf import settings
from django.db import connections


def backup_dir():
    path = Path(settings.BASE_DIR) / 'backups'
    path.mkdir(exist_ok=True)
    return path


def sqlite_path():
    db = settings.DATABASES['default']
    if not db['ENGINE'].endswith('sqlite3'):
        return None
    return Path(db['NAME'])


def create_backup_zip():
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    zip_path = backup_dir() / f'ovc-backup-{stamp}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        db_file = sqlite_path()
        if db_file and db_file.exists():
            zf.write(db_file, arcname=f'db/{db_file.name}')
            for extra in (str(db_file) + '-wal', str(db_file) + '-shm'):
                p = Path(extra)
                if p.exists():
                    zf.write(p, arcname=f'db/{p.name}')
        media = Path(settings.MEDIA_ROOT)
        if media.exists():
            for path in media.rglob('*'):
                if path.is_file():
                    zf.write(path, arcname=str(Path('media') / path.relative_to(media)))
    return zip_path


def list_backups():
    rows = []
    for path in sorted(backup_dir().glob('ovc-backup-*.zip'), reverse=True):
        rows.append({
            'name': path.name,
            'size': path.stat().st_size,
            'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'),
        })
    return rows


def restore_from_zip(zip_path):
    """Replace the local SQLite file and media from a backup zip created by this app."""
    db_file = sqlite_path()
    if db_file is None:
        raise RuntimeError('Restore is only available when this office uses SQLite.')
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        db_members = [n for n in names if n.startswith('db/') and not n.endswith('/')]
        if not db_members:
            raise RuntimeError('This zip is not an OVC CaseFile backup (no database inside).')
        connections.close_all()
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            tmp = Path(tmp)
            db_src = None
            for member in db_members:
                candidate = tmp / member
                if candidate.suffix == '.sqlite3' or candidate.name.endswith('.sqlite3'):
                    db_src = candidate
                    break
            if db_src is None:
                db_src = tmp / db_members[0]
            db_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_src, db_file)
            for suffix in ('-wal', '-shm'):
                side = Path(str(db_file) + suffix)
                if side.exists():
                    side.unlink()
            media_src = tmp / 'media'
            media_dest = Path(settings.MEDIA_ROOT)
            if media_src.exists():
                if media_dest.exists():
                    shutil.rmtree(media_dest)
                shutil.copytree(media_src, media_dest)
    return str(db_file)
