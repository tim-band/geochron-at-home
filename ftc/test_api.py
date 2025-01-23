from django.test import Client, TestCase, tag, override_settings
import django
from ftc.models import Grain, FissionTrackNumbering
from geochron.settings import SIMPLE_JWT

import abc
import json


testGrain1 = 'test/crystals/john/p1/s1/Grain01/stack-01.jpg'

simple_jwt = SIMPLE_JWT.copy()
simple_jwt['SIGNING_KEY'] = '''-----BEGIN RSA PRIVATE KEY-----
MIICYQIBAAKBgQCzuF2wX0QpHcaDtwxC1Z0aOz6FuLJPEqnIsCSfnzKihJ408Z4b
TJjBjaEnBEh5CnxMJy5dzWlcN0mpVGwGh4ED/ifHz9134mkeZ4ae4P8AvPOBxzw2
g5gRJpTyb9QmIG0Gt9zBqd7azYN5cssa5serX66ZyRJ+1iYrjtFz+jlI3wIDAQAB
AoGBAIIiavzOTs2y+M7hWeh/Q03+PiyX681kBzsBiNNodELH4sMVfdXopefpRRq6
eDvlQtHlwSY9GiCjDBynuzQTBlNpLuBt3fh3KJmgjwH57wrk4L9maTpv5owUw7DP
2FmEC2Z7FlYnchtVBRkiX4MZR9F1zNNTZvLJYNdm27R0wIKJAkUAvTMSOCJUdeX1
brfZEBa0d1Am57w5TcdWXLIp9lNUslBCDMZQB5RtekRuJKrMWK1+HFXIG/IpCjdH
Ab3etP68JN9QSHsCPQDzLIAF+5GUWI3ozNvUkKEQJSyhitCprdtoxOiQKEqDl/XM
RmLYBfqJUyu4hplUYLHaeUo2o3wyvty83e0CRE9WjTtQ2g4egk8NdU6T1tV5nPbs
LTN6dbKlW4dZ5lhn42qr9n9XNJli/LUPkmVVS17icemWILOR/oqybiOD9q2Xn3jl
Aj0AylBirxePFina3y3ZU2+E4QbcrAXu9syzt+XjS1SKMhOyp2KECBBpUelFfb9W
QBI2xnqU2QKJaTrMMcI9AkQwuNDlURgItDV/tS/WivvgmQaBqgYGQYx0IBH56/+K
eqPoe/0degy2bSamoFrli2qAd5JLMnQDVeOTxXZ40npOuGi+xQ==
-----END RSA PRIVATE KEY-----'''
simple_jwt['VERIFYING_KEY'] = '''-----BEGIN RSA PUBLIC KEY-----
MIGJAoGBALO4XbBfRCkdxoO3DELVnRo7PoW4sk8SqciwJJ+fMqKEnjTxnhtMmMGN
oScESHkKfEwnLl3NaVw3SalUbAaHgQP+J8fP3XfiaR5nhp7g/wC884HHPDaDmBEm
lPJv1CYgbQa33MGp3trNg3lyyxrmx6tfrpnJEn7WJiuO0XP6OUjfAgMBAAE=
-----END RSA PUBLIC KEY-----'''
@override_settings(SIMPLE_JWT=simple_jwt)
class JwtTestCase(TestCase):
    """
    Test code with JWT keys set so you can run the test code without setting
    JWT_PRIVATE_KEY and JWT_PUBLIC_KEY in the environment.
    """
    pass

def log_in_headers(client, username, password):
    r = client.post('/ftc/api/get-token', {
        'username': username,
        'password': password,
    })
    j = json.loads(r.content)
    return {
        'HTTP_AUTHORIZATION': 'Bearer ' + j['access'],
    }


@tag('api')
class ApiTestMixin:
    def setUp(self):
        self.headers = log_in_headers(self.client, 'counter', 'counter_password')
        self.super_headers = log_in_headers(self.client, 'super', 'super_password')

    def assertDictContainsSubset(self, a, b):
        self.assertEqual(b, {**b, **a})


@tag('api')
class ApiJwt(JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json'
    ]

    def test_api_login_failure(self):
        c = Client()
        resp1 = c.post('/ftc/api/get-token', {
            'username': 'admin',
            'password': 'not_password',
        })
        self.assertEqual(resp1.status_code, 401)

    def test_api_no_token_failure(self):
        c = Client()
        resp3 = c.get('/ftc/api/project/', HTTP_AUTHORIZATION='Bearer dddd')
        self.assertEqual(resp3.status_code, 401)

    def test_api_login_success(self):
        c = Client()
        resp1 = c.post('/ftc/api/get-token', {
            'username': 'admin',
            'password': 'admin_password',
        })
        self.assertEqual(resp1.status_code, 200)
        rts = json.loads(resp1.content)
        refresh = rts['refresh']
        resp2 = c.post('/ftc/api/refresh-token', { 'refresh': refresh })
        self.assertEqual(resp2.status_code, 200)
        rts2 = json.loads(resp2.content)
        access = rts2['access']
        resp3 = c.get('/ftc/api/project/', HTTP_AUTHORIZATION='Bearer '+access)
        self.assertEqual(resp3.status_code, 200)


@tag('api')
class ApiProjectCreate(JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json'
    ]

    def setUp(self):
        self.headers = log_in_headers(self.client, 'admin', 'admin_password')
        self.project_fields = {
            'project_name': 'pa',
            'project_description': 'test project create A',
            'priority': 5,
        }

    def test_counter_cannot_create(self):
        headers = log_in_headers(self.client, 'counter', 'counter_password')
        r2 = self.client.post('/ftc/api/project/', self.project_fields, **headers)
        self.assertEqual(r2.status_code, 403)

    def project_create(self, fields):
        r1 = self.client.post('/ftc/api/project/', fields, **self.headers)
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.get('/ftc/api/project/', **self.headers)
        self.assertEqual(r2.status_code, 200)
        ps = json.loads(r2.content)
        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0]['project_name'], fields['project_name'])
        self.assertEqual(ps[0]['project_description'], fields['project_description'])
        self.assertEqual(ps[0]['priority'], fields['priority'])
        return ps

    def test_project_create(self):
        self.project_create(self.project_fields)

    def test_project_create_for_another(self):
        user = 'counter'
        ps = self.project_create({
            'project_name': 'pa',
            'project_description': 'test project create A',
            'priority': 5,
            'user': user,
        })
        self.assertEqual(ps[0]['creator'], user)


class ApiProjectUpdate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json'
    ]

    def test_update(self):
        new_text = 'amended'
        r = self.client.patch('/ftc/api/project/2/', {
            'project_description' : new_text
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['project_name'], 'proj2') # unchanged
        self.assertEqual(j['project_description'], new_text)

    def test_cannot_update_others_project(self):
        r = self.client.patch('/ftc/api/project/1/', {
            'project_description' : 'cannot'
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_update_any_project(self):
        new_text = 'amended by super'
        r = self.client.patch('/ftc/api/project/1/', {
            'project_description' : new_text
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['project_name'], 'proj1') # unchanged
        self.assertEqual(j['project_description'], new_text)


@tag('api')
class DeleteTestBaseMixin:
    def setUp(self):
        self.headers = log_in_headers(self.client, 'counter', 'counter_password')
        self.super_headers = log_in_headers(self.client, 'super', 'super_password')

    def test_delete(self):
        r = self.client.delete('/ftc/api/'+self.path+str(self.counter_id)+'/', **self.headers)
        self.assertEqual(r.status_code, 204)
        r2 = self.client.get('/ftc/api/'+self.path, **self.super_headers)
        ps = json.loads(r2.content)
        self.assertEqual(len(ps), len(self.ids) - 1)
        actual_ids = [p['id'] for p in ps]
        expected_ids = [n for n in self.ids if n != self.counter_id]
        actual_ids.sort()
        expected_ids.sort()
        self.assertListEqual(actual_ids, expected_ids)

    def test_cannot_delete_others(self):
        r = self.client.delete('/ftc/api/'+self.path+str(self.admin_id)+'/', **self.headers)
        self.assertEqual(r.status_code, 404)
        r2 = self.client.get('/ftc/api/project/', **self.super_headers)
        ps = json.loads(r2.content)
        self.assertEqual(len(ps), len(self.ids))

    def test_superuser_can_delete_any(self):
        r = self.client.delete('/ftc/api/'+self.path+str(self.admin_id)+'/', **self.super_headers)
        self.assertEqual(r.status_code, 204)
        r2 = self.client.get('/ftc/api/'+self.path, **self.super_headers)
        ps = json.loads(r2.content)
        self.assertEqual(len(ps), len(self.ids) - 1)
        actual_ids = [p['id'] for p in ps]
        expected_ids = [n for n in self.ids if n != self.admin_id]
        actual_ids.sort()
        expected_ids.sort()
        self.assertListEqual(actual_ids, expected_ids)


class ApiProjectDelete(DeleteTestBaseMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json'
    ]
    path = 'project/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiSampleDelete(DeleteTestBaseMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json'
    ]
    path = 'sample/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiGrainDelete(DeleteTestBaseMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json',
        'grains.json'
    ]
    path = 'grain/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiImageDelete(DeleteTestBaseMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json',
        'grains.json',
        'images.json'
    ]
    path = 'image/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiSampleCreate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json'
    ]

    def setUp(self):
        super().setUp()
        self.admin_headers = log_in_headers(self.client, 'admin', 'admin_password')
        self.admin_sample_fields = {
            'sample_name': 'this_sample',
            'in_project': 1,
            'sample_property': 'T',
            'priority': 5,
            'min_contributor_num': 10,
        }

        self.counter_sample_fields = {
            'sample_name': '#4 tricky 43-sample/name(8)',
            'in_project': 1,
            'sample_property': 'T',
            'priority': 5,
            'min_contributor_num': 9,
        }

    def test_counter_cannot_create_sample_in_others_project(self):
        r = self.client.post('/ftc/api/sample/', self.admin_sample_fields, **self.headers)
        self.assertEqual(r.status_code, 403)

    def test_create_sample(self):
        r = self.client.post('/ftc/api/sample/', self.counter_sample_fields, **self.admin_headers)
        self.assertEqual(r.status_code, 201)
        j = json.loads(r.content)
        self.assertEqual(j['sample_name'], self.counter_sample_fields['sample_name'])

    def test_superuser_can_create_sample_in_others_project(self):
        r = self.client.post('/ftc/api/sample/', self.admin_sample_fields, **self.super_headers)
        self.assertEqual(r.status_code, 201)
        j = json.loads(r.content)
        self.assertEqual(j['sample_name'], self.admin_sample_fields['sample_name'])


class ApiSampleUpdate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json'
    ]

    def test_sample_update(self):
        new_priority = 23
        r = self.client.patch('/ftc/api/sample/2/', {
            'priority' : new_priority
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['sample_name'], 'counter_samp') # unchanged
        self.assertEqual(j['priority'], new_priority)

    def test_cannot_update_others_sample(self):
        r = self.client.patch('/ftc/api/sample/1/', {
            'priority' : 43
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_update_any_sample(self):
        new_priority = 22
        r = self.client.patch('/ftc/api/sample/1/', {
            'priority' : new_priority
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['sample_name'], 'adm_samp') # unchanged
        self.assertEqual(j['priority'], new_priority)

    def test_cannot_change_sample_ownership(self):
        r = self.client.patch('/ftc/api/sample/1/', {
            'in_project': 2
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_change_sample_ownership(self):
        r = self.client.patch('/ftc/api/sample/1/', {
            'in_project': 2
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['in_project'], 2)


class ApiGrainCreate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json'
    ]

    def upload_rois(self, sample_id, rois, headers):
        with open(rois, 'rb') as fh:
            return self.client.post(
                '/ftc/api/sample/' + str(sample_id) + '/grain/',
                { 'rois': fh },
                **headers,
            )

    def test_counter_cannot_create_grain_in_others_sample(self):
        r = self.upload_rois(1, 'test/crystals/john/p1/s1/Grain01/rois.json', self.headers)
        self.assertEqual(r.status_code, 403)

    def test_create_grain(self):
        rois_path = 'test/crystals/john/p1/s1/Grain01/rois.json'
        r = self.upload_rois(2, rois_path, self.headers)
        self.assertEqual(r.status_code, 201)
        j = json.loads(r.content)
        self.assertEqual(j['index'], 1)
        rr = self.client.get('/ftc/api/grain/{0}/rois/'.format(j['id']), **self.headers)
        with open(rois_path) as rfh:
            rois_expected = rfh.read()
        expected = json.loads(rois_expected)
        content = json.loads(rr.content.decode(rr.charset))
        self.assertEqual(expected['image_width'], content['image_width'])
        self.assertEqual(expected['image_height'], content['image_height'])
        self.assertEqual(len(expected['regions']), len(content['regions']))
        for i in range(len(expected['regions'])):
            self.assertEqual(expected['regions'][i]['shift'], content['regions'][i]['shift'])
            self.assertEqual(expected['regions'][i]['vertices'], content['regions'][i]['vertices'])

    def test_superuser_can_create_grain_in_others_sample(self):
        r = self.upload_rois(1, 'test/crystals/john/p1/s1/Grain01/rois.json', self.super_headers)
        self.assertEqual(r.status_code, 201)
        j = json.loads(r.content)
        self.assertEqual(j['index'], 1)


class ApiGrainUpdate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json',
        'grains.json'
    ]

    def test_grain_update_index(self):
        new_index = 23
        r = self.client.patch('/ftc/api/grain/2/', {
            'index' : new_index
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['image_width'], 502) # unchanged
        self.assertEqual(j['index'], new_index)

    def test_cannot_update_others_grain(self):
        r = self.client.patch('/ftc/api/grain/1/', {
            'index' : 43
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_update_any_grain(self):
        new_index = 22
        r = self.client.patch('/ftc/api/grain/1/', {
            'index' : new_index
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['image_width'], 402) # unchanged
        self.assertEqual(j['index'], new_index)

    def test_cannot_change_grain_ownership(self):
        r = self.client.patch('/ftc/api/grain/2/', {
            'sample': 1
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 403)

    def test_superuser_can_change_grain_ownership(self):
        r = self.client.patch('/ftc/api/grain/2/', {
            'sample': 1,
            # there is already an index 1 in sample 1, so we must
            # change the index too
            'index': 2
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['sample'], 1)


class ApiImageCreate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json',
        'grains.json'
    ]

    def upload_image(self, grain_id, image, headers):
        with open(image, 'rb') as fh:
            return self.client.post(
                '/ftc/api/grain/' + str(grain_id) + '/image/',
                { 'data': fh },
                **headers,
            )

    def test_image_create(self):
        r1 = self.upload_image(
            2,
            testGrain1,
            self.headers,
        )
        self.assertEqual(r1.status_code, 201)
        j1 = json.loads(r1.content)
        id = j1['id']
        r2 = self.client.get('/ftc/api/grain/2/image/', **self.super_headers)
        j2 = json.loads(r2.content)
        self.assertEqual(len(j2), 1)
        self.assertEqual(j2[0]['id'], id)
        r3 = self.client.get('/ftc/api/grain/1/image/', **self.super_headers)
        j3 = json.loads(r3.content)
        self.assertEqual(len(j3), 0)

    def test_cannot_create_image_for_other(self):
        r = self.upload_image(
            1,
            testGrain1,
            self.headers,
        )
        self.assertEqual(r.status_code, 403)

    def test_superuser_can_create_image_for_other(self):
        r1 = self.upload_image(
            1,
            testGrain1,
            self.super_headers,
        )
        self.assertEqual(r1.status_code, 201)
        j1 = json.loads(r1.content)
        id = j1['id']
        r2 = self.client.get('/ftc/api/grain/1/image/', **self.super_headers)
        j2 = json.loads(r2.content)
        ids = [x['id'] for x in j2]
        self.assertIn(id, ids)

class ApiImageUpdate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json',
        'grains.json',
        'images.json'
    ]

    def setUp(self):
        self.headers = log_in_headers(self.client, 'counter', 'counter_password')
        self.super_headers = log_in_headers(self.client, 'super', 'super_password')

    def test_image_update(self):
        new_index = 23
        r = self.client.patch('/ftc/api/image/2/', {
            'index' : new_index
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['index'], new_index)

    def test_cannot_update_others_grain(self):
        r = self.client.patch('/ftc/api/image/1/', {
            'index' : 43
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_update_any_image(self):
        new_index = 22
        r = self.client.patch('/ftc/api/image/1/', {
            'index' : new_index
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['index'], new_index)

    def test_cannot_change_image_ownership(self):
        r = self.client.patch('/ftc/api/image/2/', {
            'grain': 1
        }, content_type='application/json', **self.headers)
        self.assertEqual(r.status_code, 403)

    def test_superuser_can_change_image_ownership(self):
        r = self.client.patch('/ftc/api/image/2/', {
            'grain': 1,
            'index': 2
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['grain'], 1)

    def test_superuser_cannot_change_image_ownership_if_target_already_exists(self):
        with self.assertRaises(django.db.utils.IntegrityError) as cm:
            self.client.patch('/ftc/api/image/2/', {
                'grain': 1
            }, content_type='application/json', **self.super_headers)
    

class ApiCount(ApiTestMixin):
    fixtures = [
        'essential.json',
        'users.json',
        'projects.json',
        'samples.json',
        'grains.json',
        'images.json'
    ]

    @staticmethod
    @abc.abstractmethod
    def points_close(lla, llb):
        ...

    @staticmethod
    @abc.abstractmethod
    def points_from_result(result):
        ...

    @staticmethod
    @abc.abstractmethod
    def with_points(points, other):
        ...

    def setUp(self):
        super().setUp()
        logged_in = self.client.login(username='counter', password='counter_password')
        self.assertTrue(logged_in, 'failed to log in')
        r = self.client.post('/ftc/updateFtnResult/', self.with_points(self.points, {
            'sample_id': 1,
            'grain_num': 1,
            'ft_type': 'T'
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.headers = log_in_headers(self.client, 'counter', 'counter_password')

    def upload_sample_2_results(self):
        r = self.client.post('/ftc/updateFtnResult/', self.with_points(self.points2, {
            'sample_id': 2,
            'grain_num': 1,
            'ft_type': 'T'
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def test_download_count(self):
        r = self.client.get(self.count_url, {'all': True}, **self.headers)
        j = json.loads(r.content.decode(r.charset))
        jl = self.points_from_result(j[0])
        self.assertSetAlmostEqual(jl, self.points, self.points_close)
        self.assertDictContainsSubset({'id': 103, 'email': 'counter@uni.ac.uk'}, j[0]['worker'])

    def test_download_count_from_one_named_sample(self):
        self.upload_sample_2_results()
        r = self.client.get(self.count_url, {'sample': 'adm_samp'}, **self.headers)
        j = json.loads(r.content.decode(r.charset))
        jl = self.points_from_result(j[0])
        self.assertSetAlmostEqual(jl, self.points, self.points_close)
        self.assertDictContainsSubset({'id': 103, 'email': 'counter@uni.ac.uk'}, j[0]['worker'])

    def test_download_count_from_one_identified_sample(self):
        self.upload_sample_2_results()
        r = self.client.get(self.count_url, {'sample': 2}, **self.headers)
        j = json.loads(r.content.decode(r.charset))
        jl = self.points_from_result(j[0])
        self.assertSetAlmostEqual(jl, self.points2, self.points_close)
        self.assertDictContainsSubset({'id': 103, 'email': 'counter@uni.ac.uk'}, j[0]['worker'])

    def test_upload_count(self):
        """
        Uploads a count, downloads it as both latlngs and grainpoints
        (regardless of how it was uploaded) and tests that the result is the same.
        """
        latlngs = [
            [0.1, 0.5],
            [0.3, 0.4],
            [0.7, 0.1],
            [0.8, 0.6]
        ]
        sample = 2
        index = 1
        grain = Grain.objects.get(sample__pk=sample, index=index)
        points = [{
            'x_pixels': latlng[1] * grain.image_width,
            'y_pixels': grain.image_height - latlng[0] * grain.image_width,
            'category': 'track',
            'comment': ''
        } for latlng in latlngs]
        data = {
            'grain': '{0}/{1}'.format(sample, index),
            'ft_type': 'S',
            'worker': 'admin',
            'create_date': '2023-11-14',
            'grainpoints': json.dumps(points),
        }
        r = self.client.post(self.count_url, data, **self.super_headers)
        self.assertEqual(r.status_code, 201)
        # Check that we now have four points
        ftn = FissionTrackNumbering.objects.get(
            worker__username="admin",
            grain__sample__pk=sample,
            grain__index=index
        )
        self.assertEqual(ftn.result, 4)
        # Download as latlngs
        r = self.client.get('/ftc/api/countll/', {'sample': 2}, **self.headers)
        self.assertEqual(r.status_code, 200)
        jo = json.loads(r.content.decode(r.charset))
        jl = json.loads(jo[0]['latlngs'])
        self.assertListAlmostEqual(jl, latlngs)
        self.assertDictContainsSubset({'id': 102, 'email': 'admin@uni.ac.uk'}, jo[0]['worker'])
        # Download as grainpoints
        r = self.client.get('/ftc/api/count/', {'sample': 2}, **self.headers)
        self.assertEqual(r.status_code, 200)
        jo2 = json.loads(r.content.decode(r.charset))
        jgp = jo2[0]['grainpoints']
        self.assertSetAlmostEqual(jgp, points, ApiCountGrainPoint.points_close)
        self.assertDictContainsSubset({'id': 102, 'email': 'admin@uni.ac.uk'}, jo2[0]['worker'])

    def upload_contained_tracks(self, use_dict: bool):
        cts = [
            [100, 500, 300, 130, 420, 450],
            [300, 400, 250, 340, 340, 250],
        ]
        sample = 2
        index = 1
        tracks = [{
            'x1_pixels': ct[0],
            'y1_pixels': ct[1],
            'z1_level': ct[2],
            'x2_pixels': ct[3],
            'y2_pixels': ct[4],
            'z2_level': ct[5],
        } for ct in cts]
        data = {
            'grain': '{0}/{1}'.format(sample, index),
            'ft_type': 'S',
            'worker': 'admin',
            'create_date': '2024-06-26',
            'grainpoints': '[]',
            'contained_tracks': json.dumps(tracks if use_dict else cts),
        }
        r = self.client.post(self.count_url, data, **self.super_headers)
        self.assertEqual(r.status_code, 201)
        r = self.client.get(self.count_url, {'sample': 2}, **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content.decode(r.charset))
        jl = j[0]['contained_tracks']
        self.assertEqual(jl, tracks)

    def test_upload_contained_tracks_dict(self):
        self.upload_contained_tracks(True)

    def test_upload_contained_tracks_list(self):
        self.upload_contained_tracks(False)

    def test_upload_different_analysts(self):
        ctss: dict[str, list[dict]] = {
            "amy": [{
               'x1_pixels': 100,
                'y1_pixels': 200,
                'z1_level': 3,
                'x2_pixels': 400,
                'y2_pixels': 500,
                'z2_level': 6,
            }, {
               'x1_pixels': 300,
                'y1_pixels': 200,
                'z1_level': 2,
                'x2_pixels': 500,
                'y2_pixels': 400,
                'z2_level': 5,
            }],
            "bill": [{
               'x1_pixels': 123,
                'y1_pixels': 223,
                'z1_level': 4,
                'x2_pixels': 423,
                'y2_pixels': 523,
                'z2_level': 5,
            }, {
               'x1_pixels': 323,
                'y1_pixels': 223,
                'z1_level': 1,
                'x2_pixels': 523,
                'y2_pixels': 423,
                'z2_level': 2,
            }]
        }
        sample = 2
        index = 1
        data = [{
            'grain': '{0}/{1}'.format(sample, index),
            'ft_type': 'S',
            'worker': 'guest',
            'analyst': analyst,
            'create_date': '2024-07-25',
            'grainpoints': '[]',
            'contained_tracks': json.dumps(cts)
        } for analyst, cts in ctss.items()]
        for data_item in data:
            r = self.client.post(self.count_url, data_item, **self.super_headers)
            self.assertEqual(r.status_code, 201)
        r = self.client.get(self.count_url, {'sample': 2}, **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content.decode(r.charset))
        results: dict[str, list[dict[str, str]]] = {}
        for ftn in j:
            analyst = ftn["analyst"]
            line_set = results.get(analyst, list())
            line_set += ftn["contained_tracks"]
            results[analyst] = line_set
        self.assertDictsOfListsContainTheSameDicts(ctss, results)

    def test_upload_guest_no_analyst(self):
        data = {
            'grain': '2/1',
            'ft_type': 'S',
            'worker': 'guest',
            'create_date': '2024-07-25',
            'grainpoints': '[]',
            'contained_tracks': '[]'
        }
        r = self.client.post(self.count_url, data, **self.super_headers)
        self.assertEqual(r.status_code, 201)

    def assertDictsOfListsContainTheSameDicts(
        self,
        dict2ListOfDicts1: dict[str, list[dict]],
        dict2ListOfDicts2: dict[str, list[dict]]
    ):
        self.assertEqual(sorted(dict2ListOfDicts2.keys()), sorted(dict2ListOfDicts1.keys()))
        for k in dict2ListOfDicts2.keys():
            self.listsContainTheSameDicts(dict2ListOfDicts1[k], dict2ListOfDicts2[k])

    def listsContainTheSameDicts(self, listOfDicts1: list[dict], listOfDicts2: list[dict]):
        self.assertEqual(
            self.comparableListOfDicts(listOfDicts1),
            self.comparableListOfDicts(listOfDicts2)
        )

    def comparableListOfDicts(self, ds: list[dict]):
        return sorted(map(lambda x: sorted(x.items()), ds))

    def test_upload_deletes_existing(self):
        self.upload_sample_2_results()
        r = self.client.get(self.count_url, {'sample': 2}, **self.headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content.decode(r.charset))
        self.assertEqual(len(j), 1)
        # Check the correct number of points
        jl = self.points_from_result(j[0])
        self.assertEqual(len(jl), 3)
        # Check the FTN object has the correct "result"
        ftn = FissionTrackNumbering.objects.get(
            worker__username="counter",
            grain__sample__pk=2,
            grain__index=1
        )
        self.assertEqual(ftn.result, 3)
        data = {
            'grain': '2/1',
            'ft_type': 'S',
            'worker': 'counter',
            'create_date': '2023-11-14',
            'grainpoints': '[{"x_pixels": 120, "y_pixels": 123}]'
        }
        r = self.client.post(self.count_url, data, **self.headers)
        self.assertEqual(r.status_code, 201)
        r = self.client.get(self.count_url, {'sample': 2}, **self.headers)
        self.assertEqual(r.status_code, 200)
        # Should still only have one result
        j = json.loads(r.content.decode(r.charset))
        self.assertEqual(len(j), 1)
        # but this time it has just one point
        jl = self.points_from_result(j[0])
        self.assertEqual(len(jl), 1)
        ftn = FissionTrackNumbering.objects.get(
            worker__username="counter",
            grain__sample__pk=2,
            grain__index=1
        )
        self.assertEqual(ftn.result, 1)

    def assertSetAlmostEqual(self, xs, ys, cmp):
        """
        asserts that iterables xs and ys contain items similar
        enough to each other according to cmp(x,y).
        It is only guaranteed to work if there's only one item in
        x that is close to each item in y.
        """
        ss = list(xs)
        def remove_cmp(y, ss):
            for i in range(len(ss)):
                if cmp(ss[i], y):
                    ss = ss[:i] + ss[i + 1:]
                    return
            self.fail("No matching element {0} in {1}".format(y, xs))
        for y in ys:
            remove_cmp(y, ss)

    def assertListAlmostEqual(self, xs, ys):
        if type(xs) is list and type(ys) is list:
            self.assertEqual(len(xs), len(ys))
            for i in range(len(xs)):
                self.assertListAlmostEqual(xs[i], ys[i])
        else:
            self.assertAlmostEqual(xs, ys, delta=0.05)


@tag('api')
class ApiCountLatLng(ApiCount, JwtTestCase):
    count_url = '/ftc/api/countll/'
    points = [
        [0.1, 0.2],
        [0.2, 0.4],
        [0.5, 0.3]
    ]
    points2 = [
        [0.31, 0.24],
        [0.1, 0.42],
        [0.17, 0.12]
    ]
    @staticmethod
    def points_close(lla, llb):
        [lata, lnga] = lla
        [latb, lngb] = llb
        dlat = lata - latb
        dlng = lnga - lngb
        return dlat * dlat + dlng * dlng < 1e-4
    @staticmethod
    def points_from_result(result):
        return json.loads(result['latlngs'])
    @staticmethod
    def with_points(points, other):
        return {**other, 'marker_latlngs': points}


@tag('api')
class ApiCountGrainPoint(ApiCount, JwtTestCase):
    count_url = '/ftc/api/count/'
    points = [
        {"x_pixels": 100, "y_pixels": 200},
        {"x_pixels": 200, "y_pixels": 400},
        {"x_pixels": 500, "y_pixels": 300},
    ]
    points2 = [
        {"x_pixels": 310, "y_pixels": 240, "category": "track", "comment": "one"},
        {"x_pixels": 100, "y_pixels": 424, "category": "defect", "comment": "two"},
        {"x_pixels": 170, "y_pixels": 123},
    ]
    @staticmethod
    def points_close(gpa, gpb):
        dx = gpa['x_pixels'] - gpb['x_pixels']
        dy = gpa['y_pixels'] - gpb['y_pixels']
        return dx * dx + dy * dy < 1
    @staticmethod
    def points_from_result(result):
        return result['grainpoints']
    @staticmethod
    def with_points(points, other):
        return {**other, 'grainpoints': points}


class ApiGrainCreate(ApiTestMixin, JwtTestCase):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'grain_with_images5.json',
        'grain6.json'
    ]

    def test_download_roi(self):
        r = self.client.get('/ftc/api/grain/6/rois/', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content.decode(r.charset))
        self.assertDictContainsSubset({
            "stage_x": 12345,
            "stage_y": 54321,
            "mica_stage_x": 1234,
            "mica_stage_y": 4321,
            "grain_id": 6
        }, j)
        self.assertIn('regions', j)
        self.assertEqual(len(j['regions']), 1)
        self.assertDictContainsSubset({
            'shift': [10, -9],
        }, j['regions'][0])
        self.assertIn('vertices', j['regions'][0])
        self.assertSequenceEqual([
            [3, 195],
            [183, 7],
            [6, 7]
        ], j['regions'][0]['vertices'])
        self.assertIn('mica_transform_matrix', j)
        mtm = j['mica_transform_matrix']
        self.assertEqual(len(mtm), 2)
        self.assertEqual(len(mtm[0]), 3)
        self.assertEqual(len(mtm[1]), 3)
        self.assertAlmostEqual(mtm[0][0], 0.98)
        self.assertAlmostEqual(mtm[0][1], 0.2)
        self.assertAlmostEqual(mtm[0][2], -9000.9)
        self.assertAlmostEqual(mtm[1][0], 0.2)
        self.assertAlmostEqual(mtm[1][1], -0.98)
        self.assertAlmostEqual(mtm[1][2], 100.1)

    def test_download_rois_from_sample(self):
        r = self.client.get(
            '/ftc/api/rois/',
            { 'samples[]': [1] },
            **self.super_headers
        )
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content.decode(r.charset))
        self.assertEqual(len(j), 2)
        jd = { v['grain_id']:v for v in j }
        self.assertIn(1, jd)
        self.assertIn('regions', jd[1])
        self.assertEqual(len(jd[1]['regions']), 1)
        self.assertDictContainsSubset({
            'shift': [0, 0],
        }, jd[1]['regions'][0])
        self.assertIn('vertices', jd[1]['regions'][0])
        self.assertSequenceEqual([
            [2, 197],
            [197, 1],
            [1, 1]
        ], jd[1]['regions'][0]['vertices'])
        self.assertIn(5, jd)
        self.assertIn('regions', jd[5])
        self.assertEqual(len(jd[5]['regions']), 1)
        self.assertDictContainsSubset({
            'shift': [0, 0],
        }, jd[5]['regions'][0])
        self.assertIn('vertices', jd[5]['regions'][0])
        self.assertSequenceEqual([
            [2, 197],
            [197, 3],
            [1, 3]
        ], jd[5]['regions'][0]['vertices'])

    def test_download_rois_from_project(self):
        r = self.client.get(
            '/ftc/api/rois/',
            { 'projects[]': [1] },
            **self.super_headers
        )
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content.decode(r.charset))
        self.assertEqual(len(j), 3)
        jd = { v['grain_id']:v for v in j }
        self.assertIn(1, jd)
        self.assertIn('regions', jd[1])
        self.assertEqual(len(jd[1]['regions']), 1)
        self.assertIn('vertices', jd[1]['regions'][0])
        self.assertSequenceEqual([
            [2, 197],
            [197, 1],
            [1, 1]
        ], jd[1]['regions'][0]['vertices'])
        self.assertIn(5, jd)
        self.assertIn('regions', jd[5])
        self.assertEqual(len(jd[5]['regions']), 1)
        self.assertIn('vertices', jd[5]['regions'][0])
        self.assertSequenceEqual([
            [2, 197],
            [197, 3],
            [1, 3]
        ], jd[5]['regions'][0]['vertices'])
        self.assertIn(6, jd)
        self.assertIn('regions', jd[6])
        self.assertEqual(len(jd[6]['regions']), 1)
        self.assertIn('vertices', jd[6]['regions'][0])
        self.assertSequenceEqual([
            [3, 195],
            [183, 7],
            [6, 7]
        ], jd[6]['regions'][0]['vertices'])
