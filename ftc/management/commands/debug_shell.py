import logging
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse
import os
import pdb

cli = Client()
get = cli.get
post = cli.post

def login(user, password):
  login_page = reverse('account_login')
  get(login_page)
  r = post(login_page, {
    'login': user,
    'password': password
  })
  return r

class Command(BaseCommand):
  def handle(self, **options):
    login(os.getenv('SITE_ADMIN_NAME'),os.getenv('SITE_ADMIN_PASSWORD'))
    dbl = logging.getLogger('django.db.backends')
    dbl.setLevel(logging.DEBUG)
    dbl.addHandler(logging.StreamHandler())
    pdb.set_trace(header='Type c<Return> to exit')
