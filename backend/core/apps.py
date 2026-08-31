from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from django.db.backends.signals import connection_created
        connection_created.connect(_sqlite_pragmas)


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
