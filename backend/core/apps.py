import logging
import os
import sys
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from django.db.backends.signals import connection_created
        connection_created.connect(_sqlite_pragmas)
        _schedule_trocr_warmup()


def _schedule_trocr_warmup():
    """Warm TrOCR after engine start so Scan Intake does not 502 on first load."""
    if os.environ.get('OVC_SKIP_TROCR_WARMUP') == '1':
        return
    skip_cmds = {
        'test', 'migrate', 'makemigrations', 'shell', 'collectstatic',
        'check', 'flush', 'dumpdata', 'loaddata', 'createsuperuser',
    }
    if skip_cmds.intersection(sys.argv):
        return

    def _run():
        # Small delay so migrate/seed in the desktop launcher finish first.
        try:
            import time
            time.sleep(2)
            from .scan_handwrite_engines import schedule_trocr_warmup
            schedule_trocr_warmup()
        except Exception:
            logger.exception('Could not schedule TrOCR warmup')

    threading.Thread(target=_run, name='trocr-warmup-schedule', daemon=True).start()


def _sqlite_pragmas(sender, connection, **kwargs):
    """WAL + a larger cache so ~500 people / several thousand files stay snappy on one office PC."""
    if connection.vendor != 'sqlite':
        return
    cursor = connection.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')
    cursor.execute('PRAGMA synchronous=NORMAL;')
    cursor.execute('PRAGMA cache_size=-64000;')
    cursor.execute('PRAGMA temp_store=MEMORY;')
    cursor.execute('PRAGMA mmap_size=268435456;')
