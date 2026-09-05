"""Tests for backup / restore --force and production go-live commands."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.backup_ops import create_backup_zip, restore_from_zip


class BackupRestoreForceTests(SimpleTestCase):
    def test_restore_refuses_without_force_then_succeeds_with_force(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            media = tmp / 'media'
            media.mkdir()
            (media / 'case-files').mkdir()
            (media / 'case-files' / 'keep.txt').write_text('live', encoding='utf-8')
            db_file = tmp / 'db.sqlite3'
            sqlite3.connect(db_file).close()
            databases = {
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': str(db_file),
                }
            }
            with override_settings(
                MEDIA_ROOT=str(media),
                BASE_DIR=tmp,
                DATABASES=databases,
            ):
                zip_path = create_backup_zip()
                self.assertTrue(zip_path.is_file())
                with self.assertRaises(RuntimeError):
                    restore_from_zip(zip_path, force=False)
                restored = restore_from_zip(zip_path, force=True)
                self.assertTrue(Path(restored).exists())


class ProductionCommandsTests(TestCase):
    def test_disable_training_users_keeps_system_builder(self):
        User = get_user_model()
        demo = User.objects.create_user('demo.admin', password='x', is_active=True)
        builder = User.objects.create_user('OrphanCoordinator', password='x', is_active=True)
        call_command('disable_training_users')
        demo.refresh_from_db()
        builder.refresh_from_db()
        self.assertFalse(demo.is_active)
        self.assertTrue(builder.is_active)

    def test_production_check_fails_while_debug_true(self):
        with override_settings(DEBUG=True):
            with self.assertRaises(CommandError):
                call_command('production_check')
