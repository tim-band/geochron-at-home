#!/usr/bin/env python3
import argparse
import base64
import csv
from getpass import getpass
from html.parser import HTMLParser
import json
import os.path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


def parse_metadata_file(metadata, floats={}, texts={}):
    root = ET.parse(metadata).getroot()
    out = {}
    for k,v in floats.items():
        out[k] = float(root.find(v).text)
    for k,v in texts.items():
        out[k] = root.find(v).text
    return out


def parse_metadata_grain(metadata):
    """
    Loads and parses a Zeiss metadata file (so an image x.jpg might have
    a metadata file x.jpg_metadata.xml), returning a dict with the following
    (grain-specific) elements (any of which could be none):
    'image_width': Image width in pixels.
    'image_height': Image height in pixels.
    'scale_x': width of a pixel in millimeters.
    'scale_y': height of a pixel in millimeters.
    'stage_x': stage X position in millimeters.
    'stage_y': stage Y position in millimeters.

    `metadata` is a filename or file object.
    """
    xpaths_float = {
        'image_width': "Information/Image/SizeX",
        'image_height': "Information/Image/SizeY",
        'scale_x': "Scaling/Items/Distance[@Id='X']/Value",
        'scale_y': "Scaling/Items/Distance[@Id='Y']/Value",
        'stage_x': "HardwareSetting/ParameterCollection[@Id='MTBStageAxisX']/Position",
        'stage_y': "HardwareSetting/ParameterCollection[@Id='MTBStageAxisY']/Position",
    }
    return parse_metadata_file(metadata, xpaths_float)


def parse_mica_metadata_grain(metadata):
    """
    Loads and parses a Zeiss metadata file for a mica image
    'stage_x': stage X position in millimeters.
    'stage_y': stage Y position in millimeters.

    `metadata` is a filename or file object.
    """
    xpaths_float = {
        'mica_stage_x': "HardwareSetting/ParameterCollection[@Id='MTBStageAxisX']/Position",
        'mica_stage_y': "HardwareSetting/ParameterCollection[@Id='MTBStageAxisY']/Position",
    }
    return parse_metadata_file(metadata, xpaths_float)


def rlTlSwitchTranslate(lp):
    if lp == 'RLTLSwitch.RL':
        return 'R'
    if lp == 'RLTLSwitch.TL':
        return 'T'
    return None


def parse_metadata_image(metadata):
    """
    Loads and parses a Zeiss metadata file (so an image x.jpg might have
    a metadata file x.jpg_metadata.xml), returning a dict with the following
    (image-specific) elements (any of which could be none):

    'light_path': 'R' or 'T' depending on whether the image was taken using
    reflected or transmitted light.
    'focus': focus (Z) position in millimeters.

    `metadata` is a filename or file object.
    """
    xpath_text = {
        'light_path': "HardwareSetting/ParameterCollection[@Id='MTBRLTLSwitch']/PositionName"
    }
    xpaths_float = {
        'focus': "HardwareSetting/ParameterCollection[@Id='MTBFocus']/Position"
    }
    out = parse_metadata_file(metadata, xpaths_float, xpath_text)
    out['light_path'] = rlTlSwitchTranslate(out['light_path'])
    return out


def parse_transformation(transformation):
    r = []
    with open(transformation, encoding='utf-8-sig') as h:
        rows = csv.DictReader(h)
        xh = 'x' if 'x' in rows.fieldnames else 'x::x'
        yh = 'y' if 'y' in rows.fieldnames else 'y::y'
        th = 't' if 't' in rows.fieldnames else 't::t'
        for row in rows:
            x = row[xh]
            if x != '':
                r.append([float(x), float(row[yh]), float(row[th])])
    if len(r) == 2:
        return r
    raise Exception(
        "File {0} does not seem to be a transformation file".format(
            transformation
        )
    )


def generate_rois_file(dir, metadata, mica_metadata, transformation):
    vs = parse_metadata_grain(metadata)
    if mica_metadata:
        mmd = parse_mica_metadata_grain(mica_metadata)
        vs.update(mmd)
    if transformation:
        vs['mica_transform'] = parse_transformation(transformation)
    w = vs['image_width']
    h = vs['image_height']
    fname = os.path.join(dir, 'rois.json')
    x1 = int(w * 0.1)
    x2 = int(w * 0.9)
    y1 = int(h * 0.1)
    y2 = int(h * 0.9)
    vs['regions'] = [{
        'vertices': [[x1, y1], [x1, y2], [x2, y2], [x2, y1]],
        'shift': [0,0]
    }]
    with open(fname, 'w') as h:
        json.dump(vs, h)
    return fname


def generate_roiss(opts, config):
    # Find all folders containing (Refl)?Stack-(-?\d+)_metadata.xml files
    meta_re = re.compile(r'(Refl)?Stack-(-?\d+)\.[a-z]+_metadata.xml', flags=re.IGNORECASE)
    mica_meta_re = re.compile(r'Mica(Refl)?Stack-(-?\d+)\.[a-z]+_metadata.xml', flags=re.IGNORECASE)
    matrix_name = 'mica_matrix.csv'
    metadata_by_dir = {}
    for root, dirs, files in os.walk(opts.path):
        metas = [
            os.path.join(root, f)
            for f in files
            if meta_re.fullmatch(f)
        ]
        mica_metas = [
            os.path.join(root, f)
            for f in files
            if mica_meta_re.fullmatch(f)
        ]
        trans = os.path.join(root, matrix_name) if matrix_name in files else None
        if (opts.overwrite or 'rois.json' not in files):
            available = {
                'mica_transformation': trans
            }
            if mica_metas:
                available['mica_metadata']: mica_metas[0]
            if metas:
                available['metadata'] = metas[0]
                metadata_by_dir[root] = available
    for d,m in metadata_by_dir.items():
        print(d)
        print(m)
        r = generate_rois_file(
            d,
            m.get('metadata'),
            m.get('mica_metadata'),
            m.get('transformation')
        )
        print('wrote {0}'.format(r))


def get_values(d, ks):
    r = {}
    for k in ks:
        if hasattr(d, k):
            a = getattr(d, k)
            if a is not None:
                r[k] = a
    return r


def get_url(config):
    if 'url' in config:
        return config['url']
    print("A URL is required. Please use:")
    print("{0} set url <URL>".format(sys.argv[0]))
    print("for example:")
    print("{0} set url http://localhost:8000".format(sys.argv[0]))
    exit(1)


def set_config(opts, config):
    config[opts.key] = opts.value
    return config


def add_set_subparser(subparsers):
    set_parser = subparsers.add_parser('set')
    set_parser.set_defaults(func=set_config)
    set_parser.add_argument('key', help="name of the config setting to set, for example 'url'")
    set_parser.add_argument('value', help="value of the config setting to set")


def get_config(opts, config):
    if opts.key:
        print(config[opts.key])
    else:
        for (k, v) in config.items():
            if k not in ['refresh', 'access']:
                print("{0}: {1}".format(k, v))


def add_get_subparser(subparsers):
    set_parser = subparsers.add_parser('get')
    set_parser.set_defaults(func=get_config)
    set_parser.add_argument(
        '--key',
        help="name of the config setting to get, for example 'url'; the default is all of them except JWT tokens"
    )


def refresh_token(config):
    if 'refresh' not in config:
        print("Please log in:")
        print("{0} login".format(sys.argv[0]))
        exit(2)
    url = get_url(config)
    req = Request(url + "/ftc/api/refresh-token", method='POST')
    data = urlencode({
        'refresh': config['refresh']
    }).encode('ascii')
    try:
        with urlopen(req, data=data) as response:
            body = response.read()
            result = json.loads(body)
            if 'access' not in result:
                raise Exception("No access token returned")
            config['access'] = result['access']
    except HTTPError as e:
        if e.code == 403 or e.code == 401:
            print("Your login has expired. Please log in again using:")
            print("{0} login".format(sys.argv[0]))
        else:
            raise e
    return config


def token_refresh(func):
    def rf(options, config, *args, **kwargs):
        try:
            config_altered = func(options, config, *args, **kwargs)
        except HTTPError as e:
            if e.code == 403 or e.code == 401:
                refreshed_config = refresh_token(config)
                config_altered = func(options, refreshed_config, *args, **kwargs) or refreshed_config
            else:
                raise e
        return config_altered
    return rf


def login(opts, config):
    url = get_url(config)
    user = 'user' in opts and opts.user or input("username: ")
    password = 'password' in opts and opts.password or getpass()

    req = Request(url + "/ftc/api/get-token", method='POST')
    data = urlencode({
        'username': user,
        'password': password,
    }).encode('ascii')

    with urlopen(req, data=data) as response:
        #TODO: urlopen raises an HTTP Error if not-OK response is returned.
        if response.status != 200:
            raise Exception("Token acquisition failed with status {0}".format(response.status))
        body = response.read()
        result = json.loads(body)
        if 'refresh' not in result:
            raise Exception("No refresh token returned")
        config['refresh'] = result['refresh']
        if 'access' in result:
            config['access'] = result['access']

    return config


def add_login_subparser(subparsers):
    login_parser = subparsers.add_parser('login')
    login_parser.set_defaults(func=login)
    login_parser.add_argument('--password', help='password to pass, for use in scripts only')
    login_parser.add_argument('--user', help='name of the user to log in as')


def api_verb(verb, config, *args, **kwargs):
    url = get_url(config) + '/ftc/api/' + '/'.join(map(str, args))
    if kwargs:
        url += '?' + urlencode(kwargs)
    else:
        url += '/'
    req = Request(url, method=verb)
    req.add_header('Authorization', 'Bearer ' + config.get('access', ''))
    return urlopen(req)


def api_get(config, *args, **kwargs):
    return api_verb('GET', config, *args, **kwargs)


def api_post(config, *args, **kwargs):
    url = get_url(config) + '/ftc/api/' + '/'.join(map(str, args)) + '/'
    data = urlencode(kwargs)
    req = Request(url, data=data.encode('ascii'), method='POST')
    req.add_header('Authorization', 'Bearer ' + config.get('access', ''))
    return urlopen(req)


def api_upload_verb(verb, config, *args, **kwargs):
    boundary = b'auf98arnu8furpaurh83ryiruhvtbt43v!'
    url = get_url(config) + '/ftc/api/' + '/'.join(map(str, args)) + '/'
    data = b''
    for k,v in kwargs.items():
        if hasattr(v, 'read'):
            content = v.read()
            if type(content) is str:
                content = content.encode('utf-8')
            data += (
                b'--' + boundary + b'\r\nContent-Disposition: form-data;'
                + b' name="' + k.encode('ascii')
                + b'"; filename="' + quote(os.path.basename(v.name)).encode('ascii')
                + b'"\r\n\r\n' + content + b'\r\n'
            )
        else:
            data += (
                b'--' + boundary + b'\r\nContent-Disposition: form-data;'
                + b' name="' + k.encode('ascii')
                + b'"\r\n\r\n' + str(v).encode('ascii') + b'\r\n'
            )
    data += b'--' + boundary + b'--'
    req = Request(url, data=data, method=verb)
    req.add_header('Authorization', 'Bearer ' + config.get('access', ''))
    req.add_header('Content-Type', b'multipart/form-data; boundary='+boundary)
    req.add_header('Content-Length', len(data))
    return urlopen(req)


def api_upload(config, *args, **kwargs):
    return api_upload_verb('POST', config, *args, **kwargs)


@token_refresh
def project_list(opts, config):
    with api_get(config, 'project') as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list:
            for v in result:
                print(v['id'], v['project_name'])
        else:
            print(result)


@token_refresh
def project_info(opts, config):
    with api_get(config, 'project', opts.id) as response:
        body = response.read()
        result = json.loads(body)
        print('ID:', result.get('id'))
        print('name:', result.get('project_name'))
        print('creator:', result.get('creator'))
        print('creation date:', result.get('create_date'))
        print('priority:', result.get('priority'))
        print('closed:', result.get('closed'))
        samples = result.get('sample_set')
        if type(samples) is list:
            samples = ', '.join(map(str,sorted(samples)))
        print('sample IDs:', samples)
        print('description:')
        print(result.get('project_description'))


@token_refresh
def project_new(opts, config):
    o = get_values(opts, ['project_name', 'project_description', 'priority', 'closed', 'user'])
    with api_post(config, 'project', **o) as response:
        print(response.read())

def add_json_options(parser, id_help):
    parser.add_argument('id', help=id_help, type=int)
    parser.add_argument(
        '--file',
        help='output file (default standard out)',
        type=argparse.FileType('w', encoding='utf-8'),
        default=sys.stdout
    )
    parser.add_argument(
        '--indent',
        help='how many spaces to use as the indent (default 2)',
        type=int,
        default=2
    )
    parser.add_argument(
        '--compact',
        help='use compact representation',
        action='store_true'
    )


def add_project_subparser(subparsers):
    # project has verbs list, info, new, update and delete
    project_parser = subparsers.add_parser('project', help='operations on projects')
    verbs = project_parser.add_subparsers(dest='project_verb')
    verbs.required = True
    list_projects = verbs.add_parser('list', help='list projects')
    list_projects.set_defaults(func=project_list)
    info = verbs.add_parser('info', help='return information on the given project')
    info.set_defaults(func=project_info)
    info.add_argument('id', help="ID of the project to return", type=int)
    create = verbs.add_parser('new', help='create a new project')
    create.set_defaults(func=project_new)
    create.add_argument('project_name', help='Project name', metavar='name')
    create.add_argument(
        'project_description',
        help='Project description',
        metavar='description',
    )
    create.add_argument('priority', help='Priority', type=int)
    create.add_argument(
        '--user',
        help='The user that will own this project, if not you',
        type=str,
    )
    create.add_argument(
        '--closed',
        help='This project will not be shown to counters',
        action='store_true',
    )
    rois = verbs.add_parser('rois', help='download a ROI file for the grains in a project')
    rois.set_defaults(func=project_rois_download)
    add_json_options(rois, 'project ID')


@token_refresh
def sample_list(opts, config):
    kwargs = {}
    if opts.project:
        kwargs['in_project'] = opts.project
    with api_get(config, 'sample', **kwargs) as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list:
            for v in result:
                print(v['id'], v['sample_name'])
        else:
            print(result)


@token_refresh
def sample_new(opts, config):
    with api_post(config, 'sample', **get_values(opts, [
        'sample_name',
        'in_project',
        'sample_property',
        'priority',
        'min_contributor_num'
    ])) as response:
        result = json.loads(response.read())
        if 'id' in result:
            id = result['id']
            print('Created new sample with ID: {0}'.format(id))
            return id
        return None


@token_refresh
def sample_info(opts, config):
    with api_get(config, 'sample', opts.id) as response:
        body = response.read()
        print(body)


@token_refresh
def sample_upload(opts, config):
    if opts.sample_name == None:
        (dir0, name) = os.path.split(opts.dir)
        if name == '':
            (dir1, name) = os.path.split(dir0)
        bad_char = re.compile(r'[^0-9a-zA-Z_\- #/\(\):@]')
        opts.sample_name = re.sub(bad_char, '_', name)
    id = sample_new(opts, config)
    opts.sample = id
    grain_upload(opts, config)


def add_sample_subparser(subparsers):
    # sample has verbs list, info, new, update and delete
    sample_parser = subparsers.add_parser('sample', help='operations on samples')
    verbs = sample_parser.add_subparsers(dest='sample_verb')
    verbs.required = True
    list_samples = verbs.add_parser('list', help='list samples')
    list_samples.set_defaults(func=sample_list)
    list_samples.add_argument('--project', help='limit to one project')
    info = verbs.add_parser('info', help='return information on the given sample')
    info.set_defaults(func=sample_info)
    info.add_argument('id', help="ID of the project to return", type=int)
    create = verbs.add_parser('new', help='create a new sample (with no grains yet)')
    create.set_defaults(func=sample_new)
    create.add_argument(
        'sample_name',
        metavar='name',
        help='Sample name',
    )
    create.add_argument(
        'in_project',
        metavar='project_id',
        help='Numeric project ID the sample is part of'
    )
    create.add_argument(
        'sample_property',
        metavar='property',
        help='[T]est Sample, [A]ge Standard Sample, or [D]osimeter Sample',
        choices=['T', 'A', 'D'],
    )
    create.add_argument(
        'priority',
        help='Priority in showing the sample to the user (higher number means users will see it earlier)',
        default=0,
        type=int
    )
    create.add_argument(
        'min_contributor_num',
        help='Number of user contributions required',
        default=1,
        type=int
    )
    upload = verbs.add_parser('upload', help='create a new sample (uploading grains from a directory)')
    upload.set_defaults(func=sample_upload)
    upload.add_argument(
        '-k',
        '--keep-going',
        dest='keepgoing',
        action='store_true',
        help='keep going if some grains cannot be uploaded'
    )
    upload.add_argument(
        '--sample_name',
        dest='sample_name',
        metavar='name',
        help='Sample name (default is to use the directory name)',
    )
    upload.add_argument(
        'in_project',
        metavar='project_id',
        help='Numeric project ID the sample is part of'
    )
    upload.add_argument(
        'sample_property',
        metavar='property',
        help='[T]est Sample, [A]ge Standard Sample, or [D]osimeter Sample',
        choices=['T', 'A', 'D'],
    )
    upload.add_argument(
        'priority',
        help='Priority in showing the sample to the user (higher number means users will see it earlier)',
        default=0,
        type=int
    )
    upload.add_argument(
        'min_contributor_num',
        help='Number of user contributions required',
        default=1,
        type=int
    )
    upload.add_argument(
        'dir',
        help='Directory containing the grains'
    )
    rois = verbs.add_parser('rois', help='download a ROI file for the grains in a sample')
    rois.set_defaults(func=sample_rois_download)
    add_json_options(rois, 'sample ID')


@token_refresh
def grain_list(opts, config):
    with api_get(config, 'sample', opts.sample, 'grain') as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list:
            for v in result:
                print('{0}: grain {1} of sample {2}'.format(v['id'], v['index'], v['sample']))
        else:
            print(result)


@token_refresh
def grain_new(opts, config):
    with api_upload(
        config, 'sample', opts.sample, 'grain',
        rois=open(opts.rois, 'rb'),
        index=opts.index
    ) as response:
        body = response.read()
        result = json.loads(body)
        id = result['id']
        print("Created new grain", id)
        return id


def output_json(opts, object):
    v = json.loads(object)
    indent = None if opts.compact else opts.indent
    print(json.dumps(v, indent=indent), file=options.file)


@token_refresh
def project_rois_download(opts, config):
    with api_get(
        config,
        'rois',
        **{ 'project[]': opts.id }
    ) as response:
        output_json(opts, response.read())


@token_refresh
def sample_rois_download(opts, config):
    with api_get(
        config,
        'rois',
        **{ 'sample[]': opts.id }
    ) as response:
        output_json(opts, response.read())


@token_refresh
def grain_rois_download(opts, config):
    with api_get(config, 'grain', opts.id, 'rois') as response:
        output_json(opts, response.read())


@token_refresh
def grain_info(opts, config):
    with api_get(config, 'grain', opts.id) as response:
        body = response.read()
        v = json.loads(body)
        print(
            ( 'grain ID: {0}\nsample ID: {1}\nindex: {2}\n'
            + 'image size: {3} x {4}\n'
            + 'scale: {5} x {6}\nstage position: {7} x {8}\n'
        ).format(
            v.get('id'), v.get('sample'), v.get('index'),
            v.get('image_width'), v.get('image_height'),
            v.get('scale_x'), v.get('scale_y'),
            v.get('stage_x'), v.get('stage_y'),
        ))

def add_grain_subparser(subparsers):
    grain_parser = subparsers.add_parser('grain', help='operations on grains')
    verbs = grain_parser.add_subparsers(dest='grain_verb')
    verbs.required = True
    list_grains = verbs.add_parser('list', help='list grains')
    list_grains.set_defaults(func=grain_list)
    list_grains.add_argument('sample', help='report grains for this sample ID', type=int)
    create = verbs.add_parser('new', help='create a new sample with a rois.json but no images yet')
    create.set_defaults(func=grain_new)
    create.add_argument('sample', help='sample ID to add this grain to', type=int)
    create.add_argument('rois', help='path to rois.json')
    create.add_argument(
        '--index',
        help='Index of the grain within the sample (default will choose the next integer)',
        type=int
    )
    upload = verbs.add_parser(
        'upload',
        help='create multiple grains by uploading directories containing rois.json and image stack Jpegs'
    )
    upload.set_defaults(func=grain_upload)
    upload.add_argument('sample', help='Sample ID to add these grains to', type=int)
    upload.add_argument(
        'dir',
        help='directory containing directories containing rois.json files and z-stack images'
    )
    upload.add_argument(
        '-k',
        '--keep-going',
        dest='keepgoing',
        action='store_true',
        help='keep going if some grains cannot be uploaded'
    )
    info = verbs.add_parser('info', help='show information for a grain')
    info.set_defaults(func=grain_info)
    info.add_argument('id', help='grain ID', type=int)
    rois = verbs.add_parser('rois', help='download a ROI file for a grain')
    rois.set_defaults(func=grain_rois_download)
    add_json_options(rois, 'grain ID')


@token_refresh
def image_list(opts, config):
    with api_get(config, 'grain', opts.grain or '-', 'image') as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list:
            for v in result:
                print('{0}: type {1} index {2} of grain {3}'.format(
                    v.get('id'), v.get('ft_type'), v.get('index'), v.get('grain')
                ))
        else:
            print(result)


@token_refresh
def image_upload(opts, config):
    try:
        extras = parse_metadata_image(opts.image + '_metadata.xml')
    except OSError:
        extras = {}
    with api_upload(
        config, 'grain', opts.grain, 'image',
        data=open(opts.image, 'rb'), **extras
    ) as response:
        body = response.read()
        result = json.loads(body)
        print("Uploaded image", opts.image, "as image", result.get('id'))


def images_upload(opts, config):
    images = sorted(opts.image)
    last_error = None
    for attempt in [1,2,3]:
        for_retry = []
        for i in images:
            opts.image = i
            try:
                image_upload(opts, config)
            except HTTPError as e:
                last_error = e
                if 500 <= e.code:
                    for_retry.append(i)
                elif 400 <= e.code:
                    print('image {0} failed with error {1}'.format(
                        i, e.code
                    ))
        if len(for_retry) == 0:
            return
        images = for_retry
    print("Some uploads failed:", images)
    print("Last error was", last_error)


def get_name_index(name):
    for i in [-4, -3, -2, -1]:
        n = name[i:]
        if n.isnumeric():
            return int(n)
    return None


@token_refresh
def grain_upload(opts, config):
    rois_name = 'rois.json'
    n = 0
    successful = 0
    for root, dirs, files in os.walk(opts.dir):
        if rois_name in files:
            opts.rois = os.path.join(root, rois_name)
            opts.index = get_name_index(root)
            try:
                n += 1
                grain = grain_new(opts, config)
                images = [os.path.join(root, f) for f in files if os.path.splitext(f)[1] in ('.jpg', '.jpeg', '.png')]
                image_opts = argparse.Namespace(grain=grain, image=images)
                images_upload(image_opts, config)
                successful += 1
            except HTTPError as e:
                print("Failed to upload grain {0} because of error {1} ({2})".format(
                    n, e.code, e.reason
                ))
                print(opts)
                if not opts.keepgoing or e.code < 500:
                    raise e
    print("Uploaded grain count:", successful)


@token_refresh
def image_update(opts, config):
    try:
        extras = parse_metadata_image(opts.image + '_metadata.xml')
    except OSError:
        extras = {}
    with api_upload_verb(
        'PATCH',
        config,
        'image',
        opts.id,
        data=open(opts.image, 'rb'),
        grain=opts.grain,
        **extras
    ) as response:
        print(response.read())


@token_refresh
def image_info(opts, config):
    with api_get(config, 'image', opts.id) as response:
        body = response.read()
        v = json.loads(body)
        print((
            'image ID: {0}\ngrain ID: {1}\nindex: {2}\n'
            + 'fission track type: {3}\nlight path: {4}\nfocus: {5}\n'
        ).format(
            v.get('id'), v.get('grain'), v.get('index'), v.get('ft_type'),
            v.get('light_path'), v.get('focus'),
        ))


@token_refresh
def image_delete(opts, config):
    with api_verb('DELETE', config, 'image', opts.id) as response:
        print('deleted')


def add_image_subparser(subparsers):
    image_parser = subparsers.add_parser('image', help='operations on images')
    verbs = image_parser.add_subparsers(dest='image_verb')
    verbs.required = True
    list_images = verbs.add_parser('list', help='list images')
    list_images.set_defaults(func=image_list)
    list_images.add_argument('--grain', help='only report images for this grain ID')
    upload = verbs.add_parser('upload', help='upload an image for a grain')
    upload.set_defaults(func=images_upload)
    upload.add_argument('grain', help='Grain ID')
    upload.add_argument(
        'image',
        help='Paths to image files (PNG or JPG)',
        nargs='+',
    )
    info = verbs.add_parser('info', help='information about image')
    info.set_defaults(func=image_info)
    info.add_argument('id', help='Image ID')
    update = verbs.add_parser('update', help='update image')
    update.set_defaults(func=image_update)
    update.add_argument('id', help='Image ID to update')
    update.add_argument('grain', help='Grain ID')
    update.add_argument('image', help='Path to image file (PNG or JPG)')
    delete = verbs.add_parser('delete', help='delete image')
    delete.set_defaults(func=image_delete)
    delete.add_argument('id', help='Image ID to delete')


def do_flatten(x, prefix, prefix_dot):
    if type(x) is not dict:
        yield (prefix, x)
    else:
        for (k,v) in x.items():
            p = prefix_dot + k
            yield from do_flatten(v, p, p + '.')


def flatten(x):
    yield from do_flatten(x, '', '')


def find_cell(path, x):
    for p in path:
        if type(x) is dict and p in x:
            x = x[p]
        else:
            return ''
    return x


def output_as_csv(xs):
    columns = {}
    for x in xs:
        for (k,v) in flatten(x):
            columns[k] = True
    cols = columns.keys()
    print(*cols, sep=',')
    paths = [c.split('.') for c in cols]
    for x in xs:
        row = [find_cell(p, x) for p in paths]
        print(*row, sep=',')


@token_refresh
def count_list(opts, config):
    kwargs = opts.all
    if opts.sample:
        kwargs['sample'] = opts.sample
    if opts.grain:
        kwargs['grain'] = opts.grain
    with api_get(config, 'count', **kwargs) as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list:
            output_as_csv(result)
        else:
            print(result)


def add_count_subparser(subparsers):
    # count only has list for now
    count_parser = subparsers.add_parser('count', help='operations on user count results')
    verbs = count_parser.add_subparsers(dest='count_verb')
    verbs.required = True
    list_counts = verbs.add_parser('list', help='list count results')
    list_counts.set_defaults(func=count_list)
    list_counts.add_argument('--all', action='store_const', const={all:None}, default={}, help='report unfinished counts as well')
    list_counts.add_argument('--sample', help='only report the sample with this name')
    list_counts.add_argument('--grain', help='only report the grain with this index')


def add_genrois_subparser(subparsers):
    parser = subparsers.add_parser(
        'genrois',
        help='generate rois.json files from *_metadata.xml files'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='overwrite any existing rois.json files'
    )
    parser.add_argument(
        'path',
        help='path to directories containing *_metadata.xml files (at any depth)'
    )
    parser.set_defaults(func=generate_roiss)


class ExceptionExtractor(HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.levels = 0

    def handle_starttag(self, tag, attrs):
        if self.levels != 0 or ('class', 'exception_value') in attrs:
            self.levels += 1

    def handle_endtag(self, tag):
        if self.levels != 0:
            self.levels -= 1

    def handle_data(self, data):
        if self.levels != 0:
            print(data)                


def parse_argv():
    usage = "usage: %prog -s SETTINGS | --settings=SETTINGS"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c',
        '--config',
        help='configuration file',
        default='gah.config',
        dest='config',
        metavar='FILE'
    )
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True
    add_set_subparser(subparsers)
    add_get_subparser(subparsers)
    add_login_subparser(subparsers)
    add_project_subparser(subparsers)
    add_sample_subparser(subparsers)
    add_grain_subparser(subparsers)
    add_image_subparser(subparsers)
    add_count_subparser(subparsers)
    add_genrois_subparser(subparsers)
    return parser.parse_args()

def open_config(options):
    config_mode = os.path.exists(options.config) and 'r+' or 'w+'
    return open(options.config, config_mode)

def load_config(config_fh, options):
    config_file = config_fh.read()
    if len(config_file) == 0:
        return {}
    return json.loads(config_file)

def save_config(config_fh, config):
    if config:
        config_fh.seek(0)
        json.dump(config, config_fh)
        config_fh.truncate()

def perform_action(options):
    config_fh = open_config(options)
    config = load_config(config_fh, options)
    try:
        config_altered = options.func(options, config)
        save_config(config_fh, config_altered)
        config_fh.close()
    except HTTPError as e:
        print("Failed (with HTTP code {0}: {1})".format(e.code, e.reason))
        body = e.read().decode()
        ExceptionExtractor().feed(body)
        exit(1)

if __name__ == '__main__':
    options = parse_argv()
    perform_action(options)
