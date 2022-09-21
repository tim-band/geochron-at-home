import os
import re

img_ext = { '.png' : 'P', '.jpeg': 'J', '.jpg': 'J' }

upload_file_name_pattern = re.compile(
    r"^((?P<rois>rois\.json)|("
    r"((?P<mica>mica)?(?P<refl>refl)?stack"
    r"((\-(?P<z>\-?\d\d?))|(?P<flat>flat))))"
    r"(?P<ext>\.jpg|\.jpeg|\.png)"
    r"(?P<meta>_metadata.xml)?)$",
    re.IGNORECASE
)

def parse_upload_name(name):
    result = upload_file_name_pattern.match(name)
    if result is None:
        return None
    r = {
        'format': None if result.group('ext') is None else img_ext[result.group('ext')],
        'index': None if result.group('z') is None else int(result.group('z'))
    }
    for b in ['rois', 'mica', 'refl', 'flat', 'meta']:
        r[b] = result.group(b) is not None
    if r['flat']:
        r['index'] = -1 if r['refl'] else 0
    elif r['refl']:
        r['index'] = 100 - r['index']
    r['ft_type'] = 'I' if r['mica'] else 'S'
    r['is_image'] = not (r['rois'] or r['meta'])
    return r
