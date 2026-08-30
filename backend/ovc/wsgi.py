"""WSGI config for the OVC project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovc.settings')

application = get_wsgi_application()
