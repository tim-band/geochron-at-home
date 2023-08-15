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
    """
    Parses a file name (without path) producing a dictionary with keys:
    - rois: True if this is a rois.json file, False otherwise
    - mica: True if this is a mica stack image, False otherwise
    - refl: True if this is an image in reflected light, False otherwise
    - flat: True if this is the one and only image of its type (not a stack image)
    - meta: True if this is metadata, not an image (or rois)
    - is_image: True if this is an image, not metadata or rois
    - ft_type: 'I' for induced tracks (mica) or 'S' if spontaneous tracks (grains)
    - index: where in the stack this is (lower numbers are higher)
    - format: 'P' for PNG, 'J' for Jpeg, None for rois
    """
    result = upload_file_name_pattern.match(name)
    if result is None:
        return None
    r = {
        'format': None if result.group('ext') is None else img_ext[result.group('ext')],
        'index': None if result.group('z') is None else int(result.group('z'))
    }
    for b in ['rois', 'mica', 'refl', 'flat', 'meta']:
        r[b] = result.group(b) is not None
    if r['rois']:
        pass
    elif r['flat']:
        r['index'] = -1 if r['refl'] else 0
    elif r['refl']:
        r['index'] = r['index'] - 100
    r['ft_type'] = None if r['rois'] else ('I' if r['mica'] else 'S')
    r['is_image'] = not (r['rois'] or r['meta'])
    return r
