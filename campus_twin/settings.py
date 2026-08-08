"""
Django settings for campus_twin project.
"""

import os
from pathlib import Path

import dj_database_url

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------
# BASE DIRECTORY
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------
# SECURITY
# ---------------------------------------------------------

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-(d%axc71&d2%ii3b_fi@w$_&oc$k+jfr-+vg8&0!0bqvjk^cyh",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"


# ---------------------------------------------------------
# ALLOWED HOSTS
# ---------------------------------------------------------

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".vercel.app",
]

render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)

vercel_hostname = os.environ.get("VERCEL_URL", "")

if vercel_hostname:
    vercel_hostname = (
        vercel_hostname
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )

    if vercel_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_hostname)


# ---------------------------------------------------------
# VERCEL / REVERSE PROXY
# ---------------------------------------------------------

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

USE_X_FORWARDED_HOST = True


# ---------------------------------------------------------
# CSRF
# ---------------------------------------------------------

CSRF_TRUSTED_ORIGINS = [
    "https://*.vercel.app",
]

if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(
        f"https://{render_hostname}"
    )

if vercel_hostname:
    CSRF_TRUSTED_ORIGINS.append(
        f"https://{vercel_hostname}"
    )


# ---------------------------------------------------------
# APPLICATIONS
# ---------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dashboard",
]


# ---------------------------------------------------------
# MIDDLEWARE
# ---------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ---------------------------------------------------------
# URL CONFIGURATION
# ---------------------------------------------------------

ROOT_URLCONF = "campus_twin.urls"


# ---------------------------------------------------------
# TEMPLATES
# ---------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ---------------------------------------------------------
# WSGI
# ---------------------------------------------------------

WSGI_APPLICATION = "campus_twin.wsgi.application"


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------
#
# Vercel:
# DATABASE_URL -> Neon PostgreSQL
#
# Local computer:
# No DATABASE_URL -> SQLite
#
# ---------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ---------------------------------------------------------
# PASSWORD VALIDATION
# ---------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ---------------------------------------------------------
# INTERNATIONALIZATION
# ---------------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# ---------------------------------------------------------
# STATIC FILES
# ---------------------------------------------------------

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# ---------------------------------------------------------
# DEFAULT PRIMARY KEY
# ---------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------
# LOGIN SETTINGS
# ---------------------------------------------------------

LOGIN_URL = "/admin-login/"

LOGIN_REDIRECT_URL = "/admin-dashboard/"