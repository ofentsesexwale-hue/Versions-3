"""Django settings for the Offline OVC Case Management System.

Fully offline / self-hosted:
  * PostgreSQL on a plain local connection string (localhost:5432)
  * Django built-in authentication + Groups/Permissions
  * No cloud services, no external AI/OCR, no third-party auth.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from backend/.env (local, offline configuration).
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'insecure-local-dev-key-change-me')

# DEBUG is env-driven. Even when False the app must remain usable locally,
# so ALLOWED_HOSTS defaults to '*' (this is an internal, offline-only tool).
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes', 'on')

_allowed = os.environ.get('DJANGO_ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = ['*'] if _allowed.strip() == '*' else [h.strip() for h in _allowed.split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ovc.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ovc.wsgi.application'
ASGI_APPLICATION = 'ovc.asgi.application'

# --- Database: SQLite by default (offline / preview). Set USE_SQLITE=false for PostgreSQL. ---
if os.environ.get('USE_SQLITE', 'true').lower() in ('1', 'true', 'yes', 'on'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 30,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'ovc_db'),
            'USER': os.environ.get('POSTGRES_USER', 'ovc_user'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'ovc_local_pass'),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

# PBKDF2 is Django's default hasher (POPIA-aligned).
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

LANGUAGE_CODE = 'en-za'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/api/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Supporting documents live on the local disk (configurable, never in the DB).
MEDIA_URL = '/api/media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media'))

# Max upload size for supporting documents (25 MB).
MAX_UPLOAD_SIZE = 25 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg')
ALLOWED_UPLOAD_TYPES = 'PDF or PNG (JPEG scans of IDs are also accepted)'

DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# Local-only CORS (React dev server + local addresses). No public exposure.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    'https://ovc-casefiles.preview.emergentagent.com',
    'http://127.0.0.1:43141',
    'http://localhost:43141',
    'http://127.0.0.1:8001',
]

# Group / role names (also created as Django Groups).
ROLE_DATA_CAPTURER = 'data-capturer'
ROLE_CASE_WORKER = 'case-worker'
ROLE_SUPERVISOR = 'supervisor'
ROLE_ADMIN = 'admin'
ALL_ROLES = [ROLE_DATA_CAPTURER, ROLE_CASE_WORKER, ROLE_SUPERVISOR, ROLE_ADMIN]

# Seeded training logins. They only see TEST- households. Live staff never do.
TRAINING_USERNAMES = frozenset({
    'admin', 'supervisor', 'caseworker', 'caseworker2', 'capturer',
})
TRAINING_HOUSEHOLD_PREFIX = 'TEST'
LIVE_HOUSEHOLD_PREFIX = 'SI'
