from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# --- Core Django settings ---
SECRET_KEY = env("SECRET_KEY", default="insecure-secret-key-for-local-dev-only")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.identity",
    "apps.subscriptions",
    "apps.learning_content",
    "apps.content_authoring",
    "apps.execution",
    "apps.knowledge",
    "apps.adaptive",
    "apps.ai_tutor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database (Phase 6 ADR-6: PostgreSQL only) ---
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://platform_user:platform_pass@localhost:5432/platform_db",
    )
}

AUTH_USER_MODEL = "identity.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF (Phase 7) ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "apps.core.error_envelope.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 20,
}

# --- JWT / Refresh Token configuration (Phase 6 §7.K, Phase 0 §16) ---
JWT_SECRET_KEY = env("JWT_SECRET_KEY", default=SECRET_KEY)
JWT_ALGORITHM = env("JWT_ALGORITHM", default="HS256")
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=30)

# --- Verification code configuration (FR-AUTH-001, Phase 2 FLOW-AUTH-01) ---
VERIFICATION_CODE_LENGTH = env.int("VERIFICATION_CODE_LENGTH", default=6)
VERIFICATION_CODE_LIFETIME_MINUTES = env.int("VERIFICATION_CODE_LIFETIME_MINUTES", default=15)
VERIFICATION_MAX_ATTEMPTS = env.int("VERIFICATION_MAX_ATTEMPTS", default=5)

# --- Subscriptions / Payments (Phase 7 §4.9, Phase 1 §16 OD-03) ---
PAYMENT_WEBHOOK_SECRET = env("PAYMENT_WEBHOOK_SECRET", default="insecure-webhook-secret-for-local-dev-only")
SUBSCRIPTION_GRACE_PERIOD_DAYS = env.int("SUBSCRIPTION_GRACE_PERIOD_DAYS", default=7)

# --- Secure Code Execution (Phase 9 §7 provisional values, Phase 6 §7.H) ---
EXECUTION_PYTHON_BINARY = env("EXECUTION_PYTHON_BINARY", default="python3")
EXECUTION_TIMEOUT_SECONDS = env.int("EXECUTION_TIMEOUT_SECONDS", default=10)
EXECUTION_CPU_SECONDS = env.int("EXECUTION_CPU_SECONDS", default=10)
EXECUTION_MEMORY_LIMIT_BYTES = env.int("EXECUTION_MEMORY_LIMIT_BYTES", default=128 * 1024 * 1024)
EXECUTION_PIDS_LIMIT = env.int("EXECUTION_PIDS_LIMIT", default=32)
EXECUTION_OUTPUT_LIMIT_BYTES = env.int("EXECUTION_OUTPUT_LIMIT_BYTES", default=64 * 1024)
EXECUTION_MAX_CONCURRENT_PER_USER = env.int("EXECUTION_MAX_CONCURRENT_PER_USER", default=2)

# --- Knowledge & Mastery (Phase 15 — provisional, see TASK 5) ---
MASTERY_ALGORITHM_VERSION = env("MASTERY_ALGORITHM_VERSION", default="rule-based-window-v1")
MASTERY_WINDOW_SIZE = env.int("MASTERY_WINDOW_SIZE", default=8)
MASTERY_MIN_EVIDENCE_FOR_SUFFICIENCY = env.int("MASTERY_MIN_EVIDENCE_FOR_SUFFICIENCY", default=3)
MASTERY_MIN_CORRECTNESS_FOR_PROFICIENT = env.float("MASTERY_MIN_CORRECTNESS_FOR_PROFICIENT", default=0.6)
MASTERY_MIN_CORRECTNESS_FOR_MASTERED = env.float("MASTERY_MIN_CORRECTNESS_FOR_MASTERED", default=0.85)
MASTERY_MIN_STRONG_RATIO_FOR_MASTERED = env.float("MASTERY_MIN_STRONG_RATIO_FOR_MASTERED", default=0.75)
CONCEPT_FLAW_OCCURRENCE_THRESHOLD = env.int("CONCEPT_FLAW_OCCURRENCE_THRESHOLD", default=3)

# --- Adaptive Engine (Phase 16 — provisional, see TASK 6) ---
ADAPTIVE_RULESET_VERSION = env("ADAPTIVE_RULESET_VERSION", default="adaptive-ruleset-v1")
PREREQUISITE_GATE_MIN_STATE = env("PREREQUISITE_GATE_MIN_STATE", default="proficient")

# --- AI Tutor (Phase 10 — provisional, see TASK 7) ---
# AI_PROVIDER_BACKEND="none" (default): no vendor configured yet
# (Phase 12 P12-D2 explicitly unresolved) — provider always reports
# unavailable, triggering the documented Fail-Soft fallback.
AI_PROVIDER_BACKEND = env("AI_PROVIDER_BACKEND", default="none")
AI_PROVIDER_HTTP_URL = env("AI_PROVIDER_HTTP_URL", default="")
AI_PROVIDER_HTTP_TIMEOUT_SECONDS = env.int("AI_PROVIDER_HTTP_TIMEOUT_SECONDS", default=15)
AI_PROVIDER_MODEL_VERSION = env("AI_PROVIDER_MODEL_VERSION", default="unconfigured")
# Phase 10 P10-D14 — Regenerate limit explicitly deferred; provisional value.
AI_REGENERATE_MAX_ATTEMPTS = env.int("AI_REGENERATE_MAX_ATTEMPTS", default=1)
# Phase 10 P10-D13 — Solution Leakage threshold explicitly deferred; provisional value.
AI_HINT_CODE_LINE_THRESHOLD = env.int("AI_HINT_CODE_LINE_THRESHOLD", default=3)
AI_CONTEXT_MAX_CHARS = env.int("AI_CONTEXT_MAX_CHARS", default=6000)
AI_CONTEXT_LESSON_EXCERPT_CHARS = env.int("AI_CONTEXT_LESSON_EXCERPT_CHARS", default=500)
AI_CONTEXT_ERROR_HISTORY_LIMIT = env.int("AI_CONTEXT_ERROR_HISTORY_LIMIT", default=3)

# --- Redis / Celery (Phase 6 ADR-4) ---
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}