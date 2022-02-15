from django.test import Client, TestCase, tag
from ftc.models import (
    Project,
    Sample,
    Grain,
    Image
)
import json


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


@tag('api')
class ApiJwt(TestCase):
    fixtures = ['users.json']

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
class ApiProjectCreate(TestCase):
    fixtures = ['users.json']

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


class ApiProjectUpdate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json']

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


class ApiProjectDelete(DeleteTestBaseMixin, TestCase):
    fixtures = ['users.json', 'projects.json']
    path = 'project/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiSampleDelete(DeleteTestBaseMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json']
    path = 'sample/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiGrainDelete(DeleteTestBaseMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json', 'grains.json']
    path = 'grain/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiImageDelete(DeleteTestBaseMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json', 'grains.json', 'images.json']
    path = 'image/'
    ids = [1,2]
    counter_id = 2
    admin_id = 1


class ApiSampleCreate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json']

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
            'sample_name': 'another_sample',
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


class ApiSampleUpdate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json']

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


class ApiGrainCreate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json']

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
        rr = self.client.get('/ftc/api/grain/{0}/rois'.format(j['id']), **self.headers)
        with open(rois_path) as rfh:
            rois_expected = rfh.read()
        self.assertJSONEqual(rois_expected, rr.content.decode(rr.charset))

    def test_superuser_can_create_grain_in_others_sample(self):
        r = self.upload_rois(1, 'test/crystals/john/p1/s1/Grain01/rois.json', self.super_headers)
        self.assertEqual(r.status_code, 201)
        j = json.loads(r.content)
        self.assertEqual(j['index'], 1)


class ApiGrainUpdate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json', 'grains.json']

    def test_grain_update(self):
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
            'sample': 1
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['sample'], 1)


class ApiImageCreate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json', 'grains.json']

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
            'test/crystals/john/p1/s1/Grain01/stack-01.jpg',
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
            'test/crystals/john/p1/s1/Grain01/stack-01.jpg',
            self.headers,
        )
        self.assertEqual(r.status_code, 403)

    def test_superuser_can_create_image_for_other(self):
        r1 = self.upload_image(
            1,
            'test/crystals/john/p1/s1/Grain01/stack-01.jpg',
            self.super_headers,
        )
        self.assertEqual(r1.status_code, 201)
        j1 = json.loads(r1.content)
        id = j1['id']
        r2 = self.client.get('/ftc/api/grain/1/image/', **self.super_headers)
        j2 = json.loads(r2.content)
        ids = [x['id'] for x in j2]
        self.assertIn(id, ids)


class ApiImageUpdate(ApiTestMixin, TestCase):
    fixtures = ['users.json', 'projects.json', 'samples.json', 'grains.json', 'images.json']

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
            'grain': 1
        }, content_type='application/json', **self.super_headers)
        self.assertEqual(r.status_code, 200)
        j = json.loads(r.content)
        self.assertEqual(j['grain'], 1)
