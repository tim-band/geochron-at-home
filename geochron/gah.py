#!/usr/bin/env python3
import argparse
import csv
from datetime import date
from getpass import getpass
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


def trim_fieldname(fieldname):
    s = fieldname.split('::')
    if 1 < len(s):
        fieldname = s[1]
    s = fieldname.split('!!')
    if 1 < len(s):
        return s[0]
    return fieldname


def parse_transformation(transformation):
    r = []
    with open(transformation, encoding='utf-8-sig') as h:
        rows = csv.DictReader(h)
        headers = {}
        for fieldname in rows.fieldnames:
            tfn = trim_fieldname(fieldname)
            headers[tfn] = fieldname
        for row in rows:
            x = row[headers.get('x', 'x')]
            if x != '':
                r.append([
                    float(x),
                    float(row[headers.get('y', 'y')]),
                    float(row[headers.get('t', 't')])
                ])
    if len(r) == 2:
        return r
    raise Exception(
        "File {0} does not seem to be a transformation file".format(
            transformation
        )
    )


def generate_rois_object(metadata, mica_metadata, transformation):
    vs = parse_metadata_grain(metadata)
    if mica_metadata:
        mmd = parse_mica_metadata_grain(mica_metadata)
        vs.update(mmd)
    if transformation:
        vs['mica_transform'] = parse_transformation(transformation)
    w = vs['image_width']
    h = vs['image_height']
    x1 = int(w * 0.1)
    x2 = int(w * 0.9)
    y1 = int(h * 0.1)
    y2 = int(h * 0.9)
    vs['regions'] = [{
        'vertices': [[x1, y1], [x1, y2], [x2, y2], [x2, y1]],
        'shift': [0,0]
    }]
    return vs


def generate_rois_file(dir, metadata, mica_metadata, transformation):
    vs = generate_rois_object(metadata, mica_metadata, transformation)
    fname = os.path.join(dir, 'rois.json')
    with open(fname, 'w') as h:
        json.dump(vs, h)
    return fname


def find_mica_transformation(root, files):
    for name in ['mica_matrix.csv', 'matrix.csv']:
        if name in files:
            return os.path.join(root, name)
    return None


def find_grains_in_directories(path):
    """
    Finds all folders containing (Refl)?Stack-(-?\d+)_metadata.xml files or rois.json files.
    Returns a dict of directory paths to 
    """
    meta_re = re.compile(r'(Refl)?Stack-(-?\d+)\.[a-z]+_metadata.xml', flags=re.IGNORECASE)
    mica_meta_re = re.compile(r'Mica(Refl)?Stack-(-?\d+)\.[a-z]+_metadata.xml', flags=re.IGNORECASE)
    metadata_by_dir = {}
    mica_matrix_by_dir = {}
    for root, dirs, files in os.walk(path, topdown=True):
        mica_matrix = find_mica_transformation(root, files)
        if mica_matrix:
            mica_matrix_by_dir[root] = mica_matrix
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
        rois = None
        if 'rois.json' in files:
            rois = os.path.join(root, 'rois.json')
        available = {
            'rois': rois,
        }
        up = os.path.dirname(root)
        if up in mica_matrix_by_dir:
            available['mica_transformation'] = mica_matrix_by_dir[up]
        if mica_metas:
            available['mica_metadata'] = mica_metas[0]
        if metas:
            available['metadata'] = metas[0]
        if metas or rois:
            metadata_by_dir[root] = available
    return metadata_by_dir


def generate_roiss(opts, config):
    metadata_by_dir = find_grains_in_directories(opts.path)
    for d,m in metadata_by_dir.items():
        if ('metadata' in m
            and (opts.overwrite or not m.get('rois'))
        ):
            print(d)
            print(m)
            r = generate_rois_file(
                d,
                m.get('metadata'),
                m.get('mica_metadata'),
                m.get('mica_transformation')
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


def is_ok(response):
    status = response.status
    return 200 <= status and status < 300


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
        if not is_ok(response):
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


def logout(opts, config):
    config.pop('refresh', None)
    config.pop('access', None)


def add_logout_subparser(subparsers):
    logout_parser = subparsers.add_parser(
        'logout',
        help='Remove the login tokens from this config file'
    )
    logout_parser.set_defaults(func=logout)


def quote_val(v):
    return quote(str(v))


def add_headers(req, config):
    req.add_header('Authorization', 'Bearer ' + config.get('access', ''))
    req.add_header('Accept', 'application/json')


def api_verb(verb, config, *args, **kwargs):
    url = get_url(config) + '/ftc/api/' + '/'.join(map(quote_val, args))
    if kwargs:
        url += '?' + urlencode(kwargs)
    else:
        url += '/'
    req = Request(url, method=verb)
    add_headers(req, config)
    return urlopen(req)


def api_get(config, *args, **kwargs):
    return api_verb('GET', config, *args, **kwargs)


def api_post(config, *args, **kwargs):
    url = get_url(config) + '/ftc/api/' + '/'.join(map(quote_val, args)) + '/'
    data = urlencode(kwargs)
    req = Request(url, data=data.encode('ascii'), method='POST')
    add_headers(req, config)
    return urlopen(req)


def api_upload_verb(verb, config, *args, **kwargs):
    boundary = b'auf98arnu8furpaurh83ryiruhvtbt43v!'
    url = get_url(config) + '/ftc/api/' + '/'.join(map(quote_val, args)) + '/'
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
def do_sample_new(opts, config):
    return api_post(config, 'sample', **get_values(opts, [
        'sample_name',
        'in_project',
        'sample_property',
        'priority',
        'min_contributor_num'
    ]))


def try_sample_new(opts, config):
    with do_sample_new(opts, config) as response:
        result = json.loads(response.read())
        if is_ok(response):
            return result.get('id')
        else:
            print("Failed to create new sample ({0})".format(response.status))
            print(result)
            raise Exception("Failed to create new sample: {0}".format(opts.sample_name))


def sample_new(opts, config):
    with do_sample_new(opts, config) as response:
        result = json.loads(response.read())
        if 'id' in result:
            id = result['id']
            print('Created new sample with ID: {0}'.format(id))


@token_refresh
def get_sample_info(config, id_or_name):
    return api_get(config, 'sample', id_or_name)


def sample_exists(config, id_or_name):
    try:
        response = get_sample_info(config, id_or_name)
        return is_ok(response)
    except HTTPError as e:
        return False


def ensure_sample(opts, config):
    """
    Returns None if the sample given by opts.sample_name already exists,
    the new ID if it did not and we managed to create it, or raises an
    exception if it did not and we failed to create it.
    """
    if not sample_exists(config, opts.sample_name):
        return try_sample_new(opts, config)
    return None

def sample_info(opts, config):
    with get_sample_info(config, opts.id) as response:
        body = response.read()
        print(body)


@token_refresh
def sample_delete(opts, config):
    with api_verb('DELETE', config, 'sample', opts.id) as response:
        if not is_ok(response):
            print('Failed with code {0}'.format(response.status))
            body = response.read()
            print(body)


def path_to_sample_name(path):
    (dir0, name) = os.path.split(path)
    if name == '':
        name = os.path.basename(dir0)
    bad_char = re.compile(r'[^0-9a-zA-Z_\- #/\(\):@]')
    return re.sub(bad_char, '_', name)


@token_refresh
def sample_upload(opts, config):
    opts.sample = None
    grain_upload(
        opts,
        config,
        make_sample_fn=ensure_sample,
        explicit_sample_name=opts.sample_name
    )


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
    info.add_argument('id', help="ID of the project to return")
    delete = verbs.add_parser('delete', help='delete the given sample')
    delete.set_defaults(func=sample_delete)
    delete.add_argument('id', help="ID of the project to delete")
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
    upload.add_argument(
        '--genrois',
        choices=['yes', 'no', 'always'],
        default='yes',
        help=(
            'should rois.json files be generated automatically?'
            + " 'yes' (default) will result in the upload of all the grains"
            + " with metadata, 'no' will result in the upload of only grains"
            + " that already have rois.json files, 'always' will result in"
            + " any existing rois.json files being regenerated."
        )
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


def grain_new_with_id(opts, config):
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


@token_refresh
def grain_new(opts, config):
    grain_new_with_id(opts, config)
    return None


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


GRAIN_RE = None
def match_grain_index(segment):
    global GRAIN_RE
    if GRAIN_RE is None:
        GRAIN_RE = re.compile(r"grain(\d+)", re.IGNORECASE)
    return GRAIN_RE.fullmatch(segment)


def grain_id_to_path(id_or_path):
    """
    Takes a grain ID or a path to a grain on disk and returns
    the appropriate API path that regerences that grain as
    an array of strings.
    """
    if id_or_path.isnumeric():
        return ['grain', id_or_path]
    (s, g) = os.path.split(id_or_path)
    if not g:
        (s, g) = os.path.split(s)
    grain_match = match_grain_index(g)
    assert grain_match, "{0} did not match Grain<nn>".format(g)
    assert s, "need to supply a numeric ID or a directory that ends <sample_name>/Grain<nn>"
    return ['sample', path_to_sample_name(s), 'grain', grain_match.group(1)]


@token_refresh
def grain_info(opts, config):
    args = grain_id_to_path(opts.id)
    with api_get(config, *args) as response:
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


@token_refresh
def grain_delete(opts, config):
    args = grain_id_to_path(opts.id)
    with api_verb('DELETE', config, *args) as response:
        if not is_ok(response):
            print(response.read())


def add_grain_subparser(subparsers):
    grain_parser = subparsers.add_parser('grain', help='operations on grains')
    verbs = grain_parser.add_subparsers(dest='grain_verb')
    verbs.required = True
    list_grains = verbs.add_parser('list', help='list grains')
    list_grains.set_defaults(func=grain_list)
    list_grains.add_argument('sample', help='report grains for this sample ID (or sample name)')
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
        help='create multiple grains by uploading directories containing rois.json'
        + ' and image stack Jpegs. All the grains will go into the same sample.'
    )
    upload.set_defaults(func=grain_upload)
    upload.add_argument('--sample', help='Sample ID (or name) to add these grains to (default is to guess based on the directory)')
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
    upload.add_argument(
        '--genrois',
        choices=['yes', 'no', 'always'],
        default='yes',
        help=(
            'should rois.json files be generated automatically?'
            + " 'yes' (default) will result in the upload of all the grains"
            + " with metadata, 'no' will result in the upload of only grains"
            + " that already have rois.json files, 'always' will result in"
            + " any existing rois.json files being regenerated."
        )
    )
    info = verbs.add_parser('info', help='show information for a grain')
    info.set_defaults(func=grain_info)
    info.add_argument('id', help='grain ID (or file system path)')
    rois = verbs.add_parser('rois', help='download a ROI file for a grain')
    rois.set_defaults(func=grain_rois_download)
    add_json_options(rois, 'grain ID')
    delete_grain = verbs.add_parser('delete', help='delete the grain')
    delete_grain.set_defaults(func=grain_delete)
    delete_grain.add_argument('id', help='grain ID (or file system path)')


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


def get_sample_and_index_from_path(path):
    path = os.path.abspath(path)
    (p1, p0) = os.path.split(path)
    grain_match = match_grain_index(p0)
    if grain_match:
        return (path_to_sample_name(p1), grain_match.group(1))
    return (p0, None)


@token_refresh
def grain_upload(opts, config, make_sample_fn=None, explicit_sample_name=None):
    n = 0
    successful = 0
    new_samples = []
    detect_sample = not opts.sample
    metadata_by_dir = find_grains_in_directories(opts.dir)
    for root,m in metadata_by_dir.items():
        opts.rois = m.get('rois')
        if (m.get('rois') or opts.genrois == 'yes'):
            if (not opts.rois or opts.genrois == 'always'):
                opts.rois = generate_rois_file(
                    root,
                    m.get('metadata'),
                    m.get('mica_metadata'),
                    m.get('mica_transformation')
                )
            (sample, index) = get_sample_and_index_from_path(root)
            opts.index = index
            if detect_sample:
                opts.sample = sample
                if make_sample_fn is not None:
                    opts.sample_name = explicit_sample_name or sample
                    if make_sample_fn(opts, config):
                        new_samples.append(sample)
            try:
                n += 1
                grain = grain_new_with_id(opts, config)
                files = os.listdir(root)
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
        else:
            print("rois: {0} genrois: {1} metadata: {2}".format(opts.rois, opts.genrois, m))
    if 0 < len(new_samples):
        print("New samples created:")
        for ns in new_samples:
            print("  {0}".format(ns))
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
        if is_ok(response):
            print('deleted')
        else:
            print('Failed ({0})'.format(response.status))
            print(response.read())


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
    if type(x) is str and (',' in x or '\n' in x):
        x.replace('"', '""')
        x = '"{0}"'.format(x)
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
    kwargs = {}
    if opts.all:
        kwargs['all'] = True
    if opts.sample:
        kwargs['sample'] = opts.sample
    if opts.grain:
        kwargs['grain'] = opts.grain
    with api_get(config, 'count', **kwargs) as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list and not opts.json:
            output_as_csv(result)
        else:
            print(result)

def count_post(config, count):
    with api_post(
        config,
        'count',
        grain='{0}/{1}'.format(count['sample'], count['index']),
        ft_type=count['ft_type'],
        worker=count['user'],
        create_date=count['date'],
        grainpoints=json.dumps(count['points'])
    ) as response:
        body = response.read()
        result = json.loads(body)
        print(result)

@token_refresh
def count_upload(opts, config):
    with open(opts.file) as h:
        j = json.loads(h.read())
        if type(j) is list:
            for obj in j:
                count_post(config, obj)
        else:
            count_post(config, j)


def add_count_subparser(subparsers):
    # count only has list for now
    count_parser = subparsers.add_parser('count', help='operations on user count results')
    verbs = count_parser.add_subparsers(dest='count_verb')
    verbs.required = True
    list_counts = verbs.add_parser('list', help='list count results as csv or json')
    list_counts.set_defaults(func=count_list)
    list_counts.add_argument(
        '--all',
        action='store_true',
        help='report unfinished counts as well'
    )
    list_counts.add_argument('--sample', help='only report the sample with this ID or name')
    list_counts.add_argument('--grain', help='only report the grain with this index')
    list_counts.add_argument(
        '--json',
        action='store_true',
        help='report results as json (instead of CSV)'
    )
    upload_count = verbs.add_parser(
        'upload',
        help='upload csv count'
    )
    upload_count.set_defaults(func=count_upload)
    upload_count.add_argument(
        'file',
        help=(
            "JSON file containing a list of objects with keys:"
            " sample (name or ID),"
            " index (grain index within the sample),"
            " ft_type ('S' if the grain tracks are counted, 'I' for the mica),"
            " user (name or ID, the person who did the count),"
            " date (the date the count was performed on),"
            " points (list of dicts with keys x_pixels, y_pixels, and"
            " optionally category and comment)."
        )
    )


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


def parse_argv():
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
    add_logout_subparser(subparsers)
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

def render_json(j, indent=''):
    if type(j) is list:
        new_indent = indent + '- '
        for item in j:
            render_json(item, new_indent)
    elif type(j) is dict:
        new_indent = indent + '  '
        for k, v in j.items():
            print('{0}{1}:'.format(indent, k))
            render_json(v, new_indent)
    else:
        print('{0}{1}'.format(indent, j))

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
        try:
            j = json.loads(body)
            render_json(j)
        except:
            print(body)
        exit(1)

if __name__ == '__main__':
    options = parse_argv()
    perform_action(options)
