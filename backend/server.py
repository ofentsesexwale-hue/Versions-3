"""Entrypoint that exposes the Django ASGI application as `app`.

The Emergent platform supervisor runs `uvicorn server:app` on port 8001.
Locally, the NPO can instead run `python manage.py runserver`.
Both paths serve the exact same Django application.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovc.settings')

app = get_asgi_application()
application = app
