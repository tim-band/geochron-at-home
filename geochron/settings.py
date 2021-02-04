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


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG') in ['1', 'true', 'True', 'TRUE']

TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

sslOnly = os.getenv('SSL_ONLY') in ['1', 'true', 'True', 'TRUE']
SECURE_SSL_REDIRECT = sslOnly
SESSION_COOKIE_SECURE = sslOnly
CSRF_COOKIE_SECURE = sslOnly

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': '5432',
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

STATIC_URL = os.getenv('STATIC_URL') or '/static/'
STATIC_ROOT = os.getenv('STATIC_ROOT') or os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [
  os.path.join(BASE_DIR, 'vendor')
]

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

EMAIL_USE_TLS = True
EMAIL_HOST = os.getenv('OUT_EMAIL_HOST')
EMAIL_PORT = os.getenv('OUT_EMAIL_PORT')
EMAIL_HOST_USER = os.getenv('OUT_EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('OUT_EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('OUT_EMAIL_ADDR')
DEFAULT_TO_EMAIL = DEFAULT_FROM_EMAIL

## sub url
LOGIN_REDIRECT_URL = '/accounts/profile/'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/ftc/'

# social auth
USE_X_FORWARDED_HOST = True