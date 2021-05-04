#!/usr/bin/env python3
import argparse
from getpass import getpass
import json
import os.path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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


def refresh_token(config):
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
                raise "No access token returned"
            config['access'] = result['access']
    except HTTPError as e:
        if e.code == 403 or e.code == 401:
            print("Your login has expired. Please log in again using:")
            print("{0} login".format(sys.argv[0]))
        else:
            raise("HTTPError {0}: {1}", e.code, e.reason)
    return config


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
            raise "Token acquisition failed with status {0}".format(response.status)
        body = response.read()
        result = json.loads(body)
        if 'refresh' not in result:
            raise "No refresh token returned"
        config['refresh'] = result['refresh']
        if 'access' in result:
            config['access'] = result['access']

    return config


def projects(opts, config):
    url = get_url(config)
    req = Request(url + "/ftc/api/projects", method='GET')

    req.add_header('Authorization', 'Bearer ' + config['access'])

    with urlopen(req) as response:
        body = response.read()
        result = json.loads(body)
        if type(result) is list:
            for v in result:
                print(v)
        else:
            print(result)


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
set_parser = subparsers.add_parser('set')
set_parser.set_defaults(func=set_config)
set_parser.add_argument('key', help="name of the config setting to set, for example 'url'")
set_parser.add_argument('value', help="value of the config setting to set")
login_parser = subparsers.add_parser('login')
login_parser.set_defaults(func=login)
login_parser.add_argument('--password', help='password to pass, for use in scripts only')
login_parser.add_argument('--user', help='name of the user to log in as')
projects_parser = subparsers.add_parser('projects', help="lists project IDs")
projects_parser.set_defaults(func=projects)

options = parser.parse_args()

if options.func == None:
    parser.print_help()
    exit(0)

config_mode = os.path.exists(options.config) and 'r+' or 'w+'
config_fh = open(options.config, config_mode)
config_file = config_fh.read()
config = {}
if len(config_file) != 0:
    config = json.loads(config_file)

try:
    config_altered = options.func(options, config)
except HTTPError as e:
    if e.code == 403 or e.code == 401:
        refreshed_config = refresh_token(config)
        config_altered = options.func(options, refreshed_config) or refreshed_config
    else:
        raise("HTTPError {0}: {1}", e.code, e.reason)

if config_altered:
    config_fh.seek(0)
    json.dump(config_altered, config_fh)
