"""ASGI config for the OVC project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovc.settings')

application = get_asgi_application()
