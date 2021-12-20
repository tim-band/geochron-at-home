#!/usr/bin/env python3
import argparse
import base64
from getpass import getpass
from html.parser import HTMLParser
import json
import os.path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


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
                + b'"\r\n\r\n' + v.encode('ascii') + b'\r\n'
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
def project_create(opts, config):
    o = get_values(opts, ['project_name', 'project_description', 'priority', 'closed', 'user'])
    with api_post(config, 'project', **o) as response:
        print(response.read())


def add_project_subparser(subparsers):
    # project has verbs list, info, create, update and delete
    project_parser = subparsers.add_parser('project', help='operations on projects')
    verbs = project_parser.add_subparsers()
    list_projects = verbs.add_parser('list', help='list projects')
    list_projects.set_defaults(func=project_list)
    info = verbs.add_parser('info', help='return information on the given project')
    info.set_defaults(func=project_info)
    info.add_argument('id', help="ID of the project to return", type=int)
    create = verbs.add_parser('create', help='create a project')
    create.set_defaults(func=project_create)
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
def sample_create(opts, config):
    with api_post(config, 'sample', **get_values(opts, [
        'sample_name',
        'in_project',
        'sample_property',
        'priority',
        'min_contributor_num'
    ])) as response:
        print(response.read())


@token_refresh
def sample_info(opts, config):
    with api_get(config, 'sample', opts.id) as response:
        body = response.read()
        print(body)


def add_sample_subparser(subparsers):
    # sample has verbs list, info, create, update and delete
    sample_parser = subparsers.add_parser('sample', help='operations on samples')
    verbs = sample_parser.add_subparsers()
    list_samples = verbs.add_parser('list', help='list samples')
    list_samples.set_defaults(func=sample_list)
    list_samples.add_argument('--project', help='limit to one project')
    info = verbs.add_parser('info', help='return information on the given sample')
    info.set_defaults(func=sample_info)
    info.add_argument('id', help="ID of the project to return", type=int)
    create = verbs.add_parser('create', help='create a sample')
    create.set_defaults(func=sample_create)
    create.add_argument(
        'sample_name',
        metavar='name',
        help='Sample name',
    )
    create.add_argument(
        'in_project',
        metavar='project',
        help='Project ID the sample is part of'
    )
    create.add_argument(
        'sample_property',
        metavar='property',
        help='[T]est Sample, [A]ge Standard Sample, or [D]osimeter Sample',
        choices=['T', 'A', 'D'],
    )
    create.add_argument(
        'priority',
        help='Priority in showing the sample to the user',
        default=0,
        type=int
    )
    create.add_argument(
        'min_contributor_num',
        help='Number of user contributions required',
        default=1,
        type=int
    )


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
def grain_rois_upload(opts, config):
    with api_upload(
        config, 'sample', opts.sample, 'grain', rois=open(opts.rois, 'rb')
    ) as response:
        body = response.read()
        result = json.loads(body)
        id = result['id']
        print("Created new grain", id)
        return id


@token_refresh
def grain_info(opts, config):
    with api_get(config, 'grain', opts.id) as response:
        body = response.read()
        v = json.loads(body)
        print('grain ID: {0}\nsample ID: {1}\nindex: {2}\nimage size: {3} x {4}\n'.format(
            v.get('id'), v.get('sample'), v.get('index'),
            v.get('image_width'), v.get('image_height')
        ))


def add_grain_subparser(subparsers):
    grain_parser = subparsers.add_parser('grain', help='operations on grains')
    verbs = grain_parser.add_subparsers()
    list_grains = verbs.add_parser('list', help='list grains')
    list_grains.set_defaults(func=grain_list)
    list_grains.add_argument('sample', help='report grains for this sample ID', type=int)
    create = verbs.add_parser('create', help='upload a rois.json')
    create.set_defaults(func=grain_upload)
    create.add_argument('sample', help='Sample ID to add this grain to', type=int)
    create.add_argument('rois', help='Path to rois.json (or directory containing images)')
    create.add_argument(
        '--index',
        help='Index of the grain within the sample (default will choose the next integer)',
        type=int
    )
    info = verbs.add_parser('info', help='show information for a grain')
    info.set_defaults(func=grain_info)
    info.add_argument('id', help='grain ID', type=int)


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
    with api_upload(
        config, 'grain', opts.grain, 'image', data=open(opts.image, 'rb')
    ) as response:
        body = response.read()
        result = json.loads(body)
        print("Uploaded image", opts.image, "as image", result.get('id'))


def images_upload(opts, config):
    images = opts.image
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


def grain_upload(opts, config):
    rois_name = 'rois.json'
    if os.path.basename(opts.rois) == rois_name:
        return grain_rois_upload(opts, config)
    n = 0
    for root, dirs, files in os.walk(opts.rois):
        if rois_name in files:
            opts.rois = os.path.join(root, rois_name)
            grain = grain_rois_upload(opts, config)
            images = [os.path.join(root, f) for f in files if os.path.splitext(f)[1] in ('.jpg', '.jpeg', '.png')]
            image_opts = argparse.Namespace(grain=grain, image=images)
            index = get_name_index(root)
            if index is not None:
                image_opts.index = index
            images_upload(image_opts, config)
            n += 1
    print("Uploaded grain count:", n)


@token_refresh
def image_update(opts, config):
    with api_upload_verb(
        'PATCH',
        config,
        'image',
        opts.id,
        data=open(opts.image, 'rb'),
        grain=opts.grain,
    ) as response:
        print(response.read())


@token_refresh
def image_info(opts, config):
    with api_get(config, 'image', opts.id) as response:
        body = response.read()
        v = json.loads(body)
        print('image ID: {0}\ngrain ID: {1}\nindex: {2}\nfission track type: {3}\n'.format(
            v.get('id'), v.get('grain'), v.get('index'), v.get('ft_type')
        ))


@token_refresh
def image_delete(opts, config):
    with api_verb('DELETE', config, 'image', opts.id) as response:
        print('deleted')


def add_image_subparser(subparsers):
    image_parser = subparsers.add_parser('image', help='operations on images')
    verbs = image_parser.add_subparsers()
    list_images = verbs.add_parser('list', help='list images')
    list_images.set_defaults(func=image_list)
    list_images.add_argument('--grain', help='only report images for this grain ID')
    create = verbs.add_parser('create', help='upload an image for a grain')
    create.set_defaults(func=images_upload)
    create.add_argument('grain', help='Grain ID')
    create.add_argument(
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


def output_as_csv(xs):
    columns = {}
    for x in xs:
        for k in x.keys():
            columns[k] = True
    cols = columns.keys()
    print(*cols, sep=',')
    for x in xs:
        row = map(lambda c: x.get(c, ''), cols)
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
    verbs = count_parser.add_subparsers()
    list_counts = verbs.add_parser('list', help='list count results')
    list_counts.set_defaults(func=count_list)
    list_counts.add_argument('--all', action='store_const', const={all:None}, default={}, help='report unfinished counts as well')
    list_counts.add_argument('--sample', help='only report the sample with this name')
    list_counts.add_argument('--grain', help='only report the grain with this index')

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
subparsers = parser.add_subparsers()
add_set_subparser(subparsers)
add_login_subparser(subparsers)
add_project_subparser(subparsers)
add_sample_subparser(subparsers)
add_grain_subparser(subparsers)
add_image_subparser(subparsers)
add_count_subparser(subparsers)

options = parser.parse_args()

if options.func is None:
    parser.print_help()
    exit(0)

config_mode = os.path.exists(options.config) and 'r+' or 'w+'
config_fh = open(options.config, config_mode)
config_file = config_fh.read()
config = {}
if len(config_file) != 0:
    config = json.loads(config_file)

# Actually perform the action!
try:
    config_altered = options.func(options, config)
except HTTPError as e:
    print("Failed (with HTTP code {0}: {1})".format(e.code, e.reason))
    body = e.read().decode()
    ExceptionExtractor().feed(body)
    exit(1)

if config_altered:
    config_fh.seek(0)
    json.dump(config_altered, config_fh)
    config_fh.truncate()

config_fh.close()
