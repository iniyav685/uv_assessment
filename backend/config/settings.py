"""
Django settings. All environment-specific values come from environment variables
(see ../.env.example). Defaults are safe for local development only.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CELERY_TASK_ALWAYS_EAGER=(bool, False),
    LOG_LEVEL=(str, "INFO"),
    DEMO_MODE=(bool, False),
    NOTIFICATION_SIMULATED_FAILURE_RATE=(float, 0.0),
)
# Read a local .env if present (Docker Compose injects variables directly).
environ.Env.read_env(BASE_DIR.parent / ".env", overwrite=False)

SECRET_KEY = env(
    "DJANGO_SECRET_KEY", default="insecure-dev-only-key-change-me-in-every-real-environment"
)
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "django_filters",
    "corsheaders",
    # Local
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.tickets",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://helpdesk:helpdesk@localhost:5432/helpdesk",
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework -------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=1)),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# --- Celery / Redis --------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# Ack after the task finishes so a crashed worker's task is redelivered;
# tasks must therefore be idempotent.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_SOFT_TIME_LIMIT = 45
CELERY_BEAT_SCHEDULE = {
    "cleanup-orphan-attachments": {
        "task": "apps.tickets.tasks.cleanup_orphan_attachments",
        "schedule": 60 * 60,  # hourly
    },
}
# Notification delivery runs on its own queue, consumed by a dedicated worker
# (see docker-compose's `worker-notifications` service). This keeps a slow mail
# provider or a burst of retries from delaying unrelated tasks (and vice versa),
# without splitting the codebase, database or broker into a separate deployment.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.notifications.tasks.notify_activity": {"queue": "notifications"},
}

# --- Object storage (S3 in production, MinIO locally) ----------------------
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="helpdesk-attachments")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-south-1")
# Leave the endpoints and keys empty on AWS: boto3 then uses regional S3 and the IAM role.
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="")
AWS_S3_PUBLIC_ENDPOINT_URL = env("AWS_S3_PUBLIC_ENDPOINT_URL", default="")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")

ATTACHMENT_MAX_BYTES = env.int("ATTACHMENT_MAX_BYTES", default=25 * 1024 * 1024)
ATTACHMENTS_PER_COMMENT = 10
ATTACHMENT_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "application/pdf",
}
ATTACHMENT_UPLOAD_URL_TTL = 15 * 60
ATTACHMENT_DOWNLOAD_URL_TTL = 60 * 60
# Pending uploads never linked to a comment are deleted after this many hours.
ATTACHMENT_ORPHAN_HOURS = 24

# Probability (0-1) that the simulated e-mail send raises a transient error,
# to demonstrate Celery retries locally. Only applies to EMAIL_PROVIDER=console.
NOTIFICATION_SIMULATED_FAILURE_RATE = env("NOTIFICATION_SIMULATED_FAILURE_RATE")

# --- E-mail delivery (SES in production, console log locally) --------------
# "console" logs identifiers only (no addresses/content) and never actually sends -
# safe for local dev and CI. "ses" sends real e-mail via Amazon SES using boto3;
# on AWS leave AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY unset so boto3 uses the task's
# IAM role (needs ses:SendEmail), same as the S3 client above.
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="console")
AWS_SES_REGION_NAME = env("AWS_SES_REGION_NAME", default=AWS_S3_REGION_NAME)
# Must be a verified SES identity (or domain) in the target AWS account/region.
EMAIL_FROM_ADDRESS = env("EMAIL_FROM_ADDRESS", default="helpdesk@example.com")

# Exposes seeded demo accounts on the login page. Never enable in production.
DEMO_MODE = env("DEMO_MODE")
DEMO_PASSWORD = "demo12345!"

# --- Logging ---------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# --- Production hardening (enabled when DEBUG is off) ----------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
