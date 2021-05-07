import os
from random import random
os.environ['DJANGO_SETTINGS_MODULE'] = 'geochron.settings'

import django
django.setup()

from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress

site = Site.objects.get(id=1)
site.domain = os.getenv('SITE_DOMAIN')
site.name = os.getenv('SITE_NAME')
site.save()

uname = os.getenv("SITE_ADMIN_NAME")
if not User.objects.filter(username=uname).exists():
    email_addr = os.getenv("SITE_ADMIN_EMAIL")
    passwd = os.getenv("SITE_ADMIN_PASSWORD")
    user = User.objects.create_superuser(uname, email_addr, passwd)
    av = EmailAddress(user=user, email=email_addr, verified=True)
    av.save()
    print("Super user `{name}` created.".format(name=uname))

uname = os.getenv("PROJ_ADMIN_NAME")
if not User.objects.filter(username=uname).exists():
    email_addr = os.getenv("PROJ_ADMIN_EMAIL")
    passwd = os.getenv("PROJ_ADMIN_PASSWORD")
    projAdmin = User.objects.create_user(uname, email=email_addr, password=passwd)
    projAdmin.is_staff=True
    projAdmin.save()
    av = EmailAddress(user=projAdmin, email=email_addr, verified=True)
    av.save()
    print("projects upload user `{name}` created.".format(name=uname))

if not User.objects.filter(username='guest').exists():
    User.objects.create_user('guest', password=str(random()))
    print("guest user created.")

