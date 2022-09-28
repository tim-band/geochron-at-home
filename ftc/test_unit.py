from django.test import Client, TestCase, tag
from ftc.parse_image_name import parse_upload_name
import json


@tag('unit')
class TestParseUploadName(TestCase):
    def test_rois_json(self):
        d = parse_upload_name('rois.json')
        self.assertDictEqual(d, {
            'rois': True, 'mica': False, 'refl': False,
            'flat': False, 'meta': False, 'is_image': False,
            'ft_type': None, 'index': None, 'format': None
        })
    def test_refl_flat(self):
        d = parse_upload_name('ReflStackFlat.jpg')
        self.assertDictEqual(d, {
            'rois': False, 'mica': False, 'refl': True,
            'flat': True, 'meta': False, 'is_image': True,
            'ft_type': 'S', 'index': -1, 'format': 'J'
        })
    def test_stack_metadata(self):
        d = parse_upload_name('Stack-02.jpg_metadata.xml')
        self.assertDictEqual(d, {
            'rois': False, 'mica': False, 'refl': False,
            'flat': False, 'meta': True, 'is_image': False,
            'ft_type': 'S', 'index': 2, 'format': 'J'
        })
    def test_mica_refl_flat(self):
        d = parse_upload_name('MicaReflStackFlat.jpg')
        self.assertDictEqual(d, {
            'rois': False, 'mica': True, 'refl': True,
            'flat': True, 'meta': False, 'is_image': True,
            'ft_type': 'I', 'index': -1, 'format': 'J'
        })
    def test_test_files(self):
        d = parse_upload_name('stack-04.jpg')
        self.assertDictEqual(d, {
            'rois': False, 'mica': False, 'refl': False,
            'flat': False, 'meta': False, 'is_image': True,
            'ft_type': 'S', 'index': 4, 'format': 'J'
        })
