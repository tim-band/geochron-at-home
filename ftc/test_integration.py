from django.test import TestCase, tag
from django.urls import reverse

import csv
import io
import json
from random import uniform
import re

from ftc.models import TutorialPage, Sample

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
class GahCase(TestCase):
  def login(self, user, password):
    login_page = reverse('account_login')
    self.client.get(login_page)
    r = self.client.post(login_page, {
      'login': user,
      'password': password
    })
    return r

  def login_admin(self):
    self.login('admin', 'admin_password')

  def login_super(self):
    self.login('super', 'super_password')

  def login_counter(self):
    self.login('counter', 'counter_password')

  def logout(self):
    self.client.post(reverse('logout'))



class CountingCase(GahCase):
  def count_grain(self, sample, grain, count):
    r = self.client.post(
      reverse('updateFtnResult'),
      {
        'sample_id': sample,
        'grain_num': grain,
        'ft_type': 'S',
        'marker_latlngs': gen_latlngs(count)
      },
      content_type='application/json'
    )
    self.assertEqual(r.status_code, 200)

  def complete_tutorial(self):
    self.client.get(reverse('tutorial'))
    self.client.post(reverse('tutorial_result'))

  def perform_guest_count(self, grain_counts):
    self.client.get(reverse('guest_counting'))
    self.complete_tutorial()
    for ((sample, grain), count) in grain_counts.items():
      self.count_grain(sample, grain, count)
    self.logout()

  def get_total_track_count(self):
    r = self.client.post(
      reverse('getTableData'),
      { 'client_response': [
        1, 2
      ] },
      content_type='application/json'
    )
    self.assertEqual(r.status_code, 200)
    j = json.loads(r.content)
    total = 0
    for [project, sample, index, ft_type, track_count, user, datetime, area] in j['aaData']:
      total += track_count
    return total


class TestGuestCounts(CountingCase):
  fixtures = [
    'essential.json',
    'users.json', 'projects.json', 'samples.json',
    'grains.json', 'images.json', 'tutorial_pages.json'
  ]

  def test_guest_counts_are_unlimited(self):
    self.login_admin()
    base_admin = self.get_total_track_count()
    self.login_super()
    base_super = self.get_total_track_count()
    self.logout()
    s1count = 5
    s2count = 6
    guest_count = 5
    for i in range(guest_count):
      self.perform_guest_count({ (1, 1): s1count, (2, 1): s2count })
    self.login_admin()
    total = self.get_total_track_count()
    # should get the results from sample 1 which is owned by admin
    self.assertEqual(total, base_admin + guest_count * s1count)
    self.logout()
    self.login_super()
    total = self.get_total_track_count()
    # should get the results from all samples
    self.assertEqual(total, base_super + guest_count * (s1count + s2count))


class TestCountJsonDownload(CountingCase):
  fixtures = [
    'essential.json',
    'users.json', 'projects.json', 'samples.json',
    'grains.json', 'grains2.json', 'images.json',
    'results.json', 'results2.json'
  ]

  def get_json_results(self, samples=None):
    if samples is None:
      r = self.client.get(reverse('getJsonResults'))
    else:
      r = self.client.get(
        reverse('getJsonResults'),
        { 'samples[]': samples }
      )
    return {
      g['grain']: g
      for g in json.loads(r.content)
    }

  def sorted_results_for_grain(self, grain):
    return sorted([
      result['result'] for result in grain['results']
    ])

  def test_superuser_downloads_all_grains(self):
    self.login_super()
    grains = self.get_json_results()
    assert(sorted(grains.keys()) == [1, 2, 3, 4])
    assert(self.sorted_results_for_grain(grains[1]) == [3, 3])
    assert(self.sorted_results_for_grain(grains[2]) == [2, 2, 3, 3])
    assert(self.sorted_results_for_grain(grains[3]) == [2])
    assert(self.sorted_results_for_grain(grains[4]) == [2])

  def test_admin_downloads_only_her_grains(self):
    self.login_admin()
    grains = self.get_json_results()
    assert(sorted(grains.keys()) == [1, 3, 4])
    assert(self.sorted_results_for_grain(grains[1]) == [3, 3])
    assert(self.sorted_results_for_grain(grains[3]) == [2])
    assert(self.sorted_results_for_grain(grains[4]) == [2])

  def test_many_samples(self):
    self.login_super()
    grains = self.get_json_results(['1', '2'])
    assert(sorted(grains.keys()) == [1, 2, 3, 4])
    assert(self.sorted_results_for_grain(grains[1]) == [3, 3])
    assert(self.sorted_results_for_grain(grains[2]) == [2, 2, 3, 3])
    assert(self.sorted_results_for_grain(grains[3]) == [2])
    assert(self.sorted_results_for_grain(grains[4]) == [2])

  def test_superuser_downloads_any_grains(self):
    self.login_super()
    grains = self.get_json_results(['2'])
    assert(sorted(grains.keys()) == [2])
    assert(self.sorted_results_for_grain(grains[2]) == [2, 2, 3, 3])

  def test_admin_cannot_download_others_results(self):
    self.login_admin()
    grains = self.get_json_results(['2'])
    assert(sorted(grains.keys()) == [])

class TestCountCsvDownload(CountingCase):
  fixtures = [
    'essential.json',
    'users.json', 'projects.json', 'samples.json',
    'grains.json', 'grains2.json', 'images.json',
    'results.json', 'results2.json'
  ]

  def get_csv_results(self, samples=None):
    if samples is None:
      r = self.client.get(reverse('getCsvResults'))
    else:
      r = self.client.get(
        reverse('getCsvResults'),
        { 'samples[]': samples }
      )
    dicts = csv.DictReader(io.StringIO(r.content.decode('utf-8')))
    res = {}
    for row in dicts:
      psi = (row['project_name'], row['sample_name'], row['index'])
      c = int(row['count'])
      if psi in res:
        res[psi].append(c)
      else:
        res[psi] = [c]
    return res

  def test_superuser_downloads_csv_all_grains(self):
    self.login_super()
    grains = self.get_csv_results()
    assert(sorted(grains.keys()) == [
      ("proj1", "adm_samp", '1'),
      ("proj1", "adm_samp", '2'),
      ("proj1", "adm_samp", '3'),
      ("proj2", "counter_samp", '1')
    ])
    assert(sorted(grains[("proj1", "adm_samp", '1')]) == [3, 3])
    assert(sorted(grains[("proj1", "adm_samp", '2')]) == [2])
    assert(sorted(grains[("proj1", "adm_samp", '3')]) == [2])
    assert(sorted(grains[("proj2", "counter_samp", '1')]) == [2, 2, 3, 3])


class RegionCase(GahCase):
  fixtures = [
    'essential.json',
    'grain_with_images.json',
    'grain_with_images5.json',
    'grain6.json'
  ]

  def setUp(self):
    self.login_admin()

  def test_download_grain_rois(self):
    r = self.client.get(
      reverse('download_grain_rois', kwargs={ 'pk': 5 })
    )
    self.assertContains(r, '', status_code=200)
    roi = json.loads(r.content)
    self.assertDictContainsSubset({
      'grain_id': 5
    }, roi)
    self.assertIn('regions', roi)
    self.assertEqual(len(roi['regions']), 1)
    self.assertEqual([
      [2, 197],
      [197, 3],
      [1, 3]
    ], roi['regions'][0]["vertices"])

  def test_download_sample_roiss(self):
    r = self.client.get(
      reverse('download_roiss'),
      { 'samples[]': [1] }
    )
    self.assertContains(r, '', status_code=200)
    j = json.loads(r.content)
    self.assertEqual(len(j), 2)
    rois = {
      region['grain_id']: region
      for region in j
    }
    self.assertIn(1, rois)
    self.assertIn('regions', rois[5])
    self.assertEqual(len(rois[5]['regions']), 1)
    self.assertEqual([
      [2, 197],
      [197, 3],
      [1, 3]
    ], rois[5]['regions'][0]["vertices"])
    self.assertIn(5, rois)
    self.assertIn('regions', rois[5])
    self.assertEqual(len(rois[5]['regions']), 1)
    self.assertEqual([
      [2, 197],
      [197, 3],
      [1, 3]
    ], rois[5]['regions'][0]["vertices"])

  def test_download_project_roiss(self):
    r = self.client.get(
      reverse('download_roiss'),
      { 'projects[]': [1] }
    )
    self.assertContains(r, '', status_code=200)
    j = json.loads(r.content)
    self.assertEqual(len(j), 3)
    rois = {
      region['grain_id']: region
      for region in j
    }
    self.assertIn(1, rois)
    self.assertIn(5, rois)
    self.assertIn(6, rois)
    self.assertIn('regions', rois[6])
    self.assertEqual(len(rois[6]['regions']), 1)
    self.assertEqual([
      [3, 195],
      [183, 7],
      [6, 7]
    ], rois[6]['regions'][0]["vertices"])

class TutorialPageCase(GahCase):
  fixtures = [
    'essential.json',
    'users.json',
    'counter_verification.json',
    'projects.json',
    'samples.json',
    'grains.json',
    'grain1_region.json',
    'tutorial_pages.json'
  ]
  def test_modifying_results_does_not_delete_tutorial_page(self):
    self.login_super()
    tps = TutorialPage.objects.all()
    self.assertEqual(len(tps), 1, 'precondition failed, should be one tutorial page')
    tp_pk = tps[0].pk
    r = self.client.post(
      reverse('updateFtnResult'),
      {
        'sample_id': 1,
        'grain_num': 1,
        'ft_type': 'S',
        'marker_latlngs': gen_latlngs(4)
      },
      content_type='application/json'
    )
    self.assertEqual(r.status_code, 200)
    tps = TutorialPage.objects.all()
    self.assertEqual(len(tps), 1, 'should still be one tutorial page')
    self.assertEqual(tps[0].pk, tp_pk, 'tutorial page changed')

  def get_tutorial_page_grain_info(self, pk):
    r = self.client.get(reverse('tutorial_page', kwargs={'pk': pk}))
    content = r.content.decode('utf-8')
    grain_info_json = re.search(r"grain_info:\s*JSON.parse\('(.*)'\)", content).group(1)
    grain_info_json = grain_info_json.replace("\\u0022", '"')
    return json.loads(grain_info_json)

  def test_adding_count_does_not_change_tutorial(self):
    self.login_counter()
    grain_info = self.get_tutorial_page_grain_info(1)
    self.assertEqual(len(grain_info["points"]), 3)
    r = self.client.post(
      reverse('updateFtnResult'),
      {
        'sample_id': 1,
        'grain_num': 1,
        'ft_type': 'S',
        'marker_latlngs': gen_latlngs(2)
      },
      content_type='application/json'
    )
    self.assertEqual(r.status_code, 200)
    grain_info = self.get_tutorial_page_grain_info(1)
    self.assertEqual(len(grain_info["points"]), 3)
    r = self.client.post(
      reverse('updateFtnResult'),
      {
        'sample_id': 1,
        'grain_num': 1,
        'ft_type': 'S',
        'marker_latlngs': gen_latlngs(6)
      },
      content_type='application/json'
    )
    grain_info = self.get_tutorial_page_grain_info(1)
    self.assertEqual(len(grain_info["points"]), 3)

class PublicPageCase(GahCase):
  fixtures = [
    'essential.json',
    'users.json',
    'projects.json',
    'samples.json',
    'grains.json',
    'results.json',
    'images.json',
    'grain1_region.json',
    'grain1_region_hole.json'
  ]
  def test_sample_publicness_controls_access_to_public_page(self):
    self.login_counter()
    r = self.client.get(
      reverse('public_sample', kwargs={ 'sample': 1, 'grain': 1 })
    )
    self.assertEqual(r.status_code, 403)
    s = Sample.objects.get(pk=1)
    s.public = True
    s.save()
    r = self.client.get(
      reverse('public_sample', kwargs={ 'sample': 1, 'grain': 1 })
    )
    self.assertEqual(r.status_code, 200)

  def test_sample_publicness_controls_access_to_grain_image(self):
    self.login_counter()
    r = self.client.get(
      reverse('get_image', kwargs={ 'pk': 1 })
    )
    self.assertEqual(r.status_code, 403)
    s = Sample.objects.get(pk=1)
    s.public = True
    s.save()
    r = self.client.get(
      reverse('get_image', kwargs={ 'pk': 1 })
    )
    self.assertEqual(r.status_code, 200)

  def test_public_markers(self):
    self.login_counter()
    s = Sample.objects.get(pk=1)
    s.public = True
    s.save()
    r = self.client.get(
      reverse('public_sample', kwargs={ 'sample': 1, 'grain': 1 })
    )
    self.assertEqual(r.status_code, 200)
    content = r.content.decode('utf-8')
    grain_info_json = re.search(r"grain_info:\s*JSON.parse\('(.*)'\)", content).group(1)
    grain_info_json = grain_info_json.replace("\\u0022", '"')
    j = json.loads(grain_info_json)
    latlngs = j['marker_latlngs']
    # There are three points; one is outside the ROI, one is in the hole
    self.assertEqual(len(latlngs), 1)
