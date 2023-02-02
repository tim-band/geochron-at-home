from django.test import Client, TestCase, tag
from django.urls import reverse

import json
from random import uniform

def gen_latlng():
  return [
    uniform(0.1, 0.9),
    uniform(0.1, 0.9)
  ]

def gen_latlngs(n):
  r = []
  for i in range(n):
    r.append(gen_latlng())
  return r

@tag('integration')
class TestGuestCounts(TestCase):
  fixtures = [
    'users.json', 'projects.json', 'samples.json',
    'grains.json', 'images.json'
  ]

  def count_grain(self, sample, grain, count):
    self.client.post(
      reverse('updateTFNResult'),
      { 'counting_res': {
        'sample_id': sample,
        'grain_num': grain,
        'ft_type': 'S',
        'track_num': count,
        'marker_latlngs': gen_latlngs(count)
      }},
      content_type='application/json'
    )

  def logout(self):
    self.client.post(reverse('logout'))

  def perform_guest_count(self):
    self.client.get(reverse('guest_counting'))
    self.client.get(reverse('tutorial'))
    self.client.post(reverse('tutorial_result'))
    self.count_grain(1, 1, 5)
    self.count_grain(2, 1, 6)
    self.logout()

  def login(self, user, password):
    login_page = reverse('account_login')
    self.client.get(login_page)
    r = self.client.post(login_page, {
      'login': user,
      'password': password
    })
    return r

  def get_total_track_count(self):
    r = self.client.post(
      reverse('getTableData'),
      { 'client_response': [
        1, 2
      ] },
      content_type='application/json'
    )
    assert(r.status_code == 200)
    j = json.loads(r.content)
    total = 0
    for [project, sample, index, ft_type, track_count, user, datetime] in j['aaData']:
      total += track_count
    return total

  def test_guest_counts_are_unlimited(self):
    self.perform_guest_count()
    self.perform_guest_count()
    self.perform_guest_count()
    self.perform_guest_count()
    self.perform_guest_count()
    self.login('admin', 'admin_password')
    total = self.get_total_track_count()
    # should get the results from sample 1 whcih is owned by admin
    assert(total == 5 * 5)
    self.logout()
    self.login('super', 'super_password')
    total = self.get_total_track_count()
    # should get the results from sample 1 whcih is owned by admin
    assert(total == 5 * (5 + 6))
