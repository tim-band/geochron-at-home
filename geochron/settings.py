"""
Django settings for geochron project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

from datetime import timedelta

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG') not in ['0', 'false', 'False', 'FALSE', 'no', 'No', 'NO']

TEMPLATE_DEBUG = DEBUG

allowed_hosts = os.getenv('ALLOWED_HOSTS') or '127.0.0.1,localhost,testserver'
ALLOWED_HOSTS = allowed_hosts.split(',')

sslOnly = os.getenv('SSL_ONLY') in ['1', 'true', 'True', 'TRUE']
SECURE_SSL_REDIRECT = sslOnly
SESSION_COOKIE_SECURE = sslOnly
CSRF_COOKIE_SECURE = sslOnly

# JWT support needs to be disabled in VSCode debugger becuase
# it can't handle newlines in environment variables, which we need
# for JWT tokens.
if not DEBUG or not os.getenv("DISABLE_JWT"):
    SIMPLE_JWT = {
        'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
        'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
        'ROTATE_REFRESH_TOKENS': False,
        'BLACKLIST_AFTER_ROTATION': False,
        'UPDATE_LAST_LOGIN': False,

        'ALGORITHM': 'RS256',
        'SIGNING_KEY': os.getenv('JWT_PRIVATE_KEY'),
        'VERIFYING_KEY': os.getenv('JWT_PUBLIC_KEY'),
        'AUDIENCE': None,
        'ISSUER': None,

        'AUTH_HEADER_TYPES': ('Bearer',),
        'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
        'USER_ID_FIELD': 'id',
        'USER_ID_CLAIM': 'user_id',

        'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
        'TOKEN_TYPE_CLAIM': 'token_type',

        'JTI_CLAIM': 'jti',

        'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
        'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
        'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
    }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'EXCEPTION_HANDLER': 'ftc.apiviews.explicit_exception_handler'
}

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ftc',
    # The Django sites framework is required
    'django.contrib.sites',
    # The Django rest framework
    'rest_framework',
    'rest_framework.authtoken',
    # Export metrics for Prometheus
    'django_prometheus',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # ... include the providers you want to enable:
    'allauth.socialaccount.providers.google',
    #'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.twitter',
    #'allauth.socialaccount.providers.linkedin',
    'allauth.socialaccount.providers.linkedin_oauth2',
    #'allauth.socialaccount.providers.openid',
)

SITE_ID = 1

# https://docs.djangoproject.com/en/3.1/ref/middleware/#middleware-ordering

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'geochron.urls'

WSGI_APPLICATION = 'geochron.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': ['templates'],
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
            ]
        }
    },
]

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django_prometheus.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        #'NAME': 'test_geochron',  # use this to dump test data!
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': int(os.getenv('DB_PORT') or 5432),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = os.getenv('STATIC_URL') or 'static/'
www_root = os.getenv('WWW_ROOT')
static_path = [www_root] if www_root else []
static_path.append('static')
STATIC_ROOT = os.getenv('STATIC_ROOT') or os.path.join(*static_path)
STATICFILES_DIRS = [
  os.path.join(BASE_DIR, 'vendor'),
]
if not os.path.isabs(STATIC_ROOT):
    STATIC_ROOT = os.path.join(BASE_DIR, STATIC_ROOT)

#
TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]

#allauth
TEMPLATE_CONTEXT_PROCESSORS = (
    # for messages
    "django.contrib.messages.context_processors.messages",
    # Required by allauth template tags
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.request", 
    # allauth specific context processors
    "allauth.account.context_processors.account",
    "allauth.socialaccount.context_processors.socialaccount",
)

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by e-mail
    "allauth.account.auth_backends.AuthenticationBackend",
)

ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_REQUIRED = True

SOCIALACCOUNT_PROVIDERS = \
    { 'google':
        { 'SCOPE': ['https://www.googleapis.com/auth/userinfo.profile'],
          'AUTH_PARAMS': { 'access_type': 'online' }
        }
    }

# email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_USE_TLS = os.getenv('FAKE_MAIL_SERVER') in [None, "false", "False", "0", ""]
EMAIL_HOST = os.getenv('OUT_EMAIL_HOST')
EMAIL_PORT = os.getenv('OUT_EMAIL_PORT')
EMAIL_HOST_USER = os.getenv('OUT_EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('OUT_EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('OUT_EMAIL_ADDR')
DEFAULT_TO_EMAIL = DEFAULT_FROM_EMAIL

## sub url
LOGIN_REDIRECT_URL = 'profile'
LOGIN_URL = 'account_login'
LOGOUT_REDIRECT_URL = 'home'

# social auth
USE_X_FORWARDED_HOST = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
#        'level': 'DEBUG',  # use this to see HTTP requests and responses
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
IMAGE_UPLOAD_SIZE_LIMIT = os.getenv('IMAGE_UPLOAD_SIZE_LIMIT') or 256 * 1024
PROMETHEUS_EXPORT_MIGRATIONS = False
prom_port_range = os.getenv('PROMETHEUS_METRICS_EXPORT_PORT_RANGE')
if prom_port_range is not None:
    (start, end) = prom_port_range.split('-',1)
    PROMETHEUS_METRICS_EXPORT_PORT_RANGE = range(int(start), int(end))
    PROMETHEUS_METRICS_EXPORT_ADDRESS = ''
