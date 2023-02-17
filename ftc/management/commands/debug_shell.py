import logging
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse
import pdb

dbl = logging.getLogger('django.db.backends')
dbl.setLevel(logging.DEBUG)
dbl.addHandler(logging.StreamHandler())

cli = Client()
get = cli.get
post = cli.post

class Command(BaseCommand):
  def handle(self, **options):
    pdb.set_trace()
