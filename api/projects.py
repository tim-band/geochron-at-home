#!/usr/bin/env python3
from json import loads
from optparse import OptionParser
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

def list_projects(url):
    req = Request(url + "/ftc/api/projects", method='GET')

    with open('access.token', 'r') as fh:
        access = fh.read()

    req.add_header('Authorization', 'Bearer ' + access)
    print("Bearer "+access+"<<<<")

    with urlopen(req) as response:
        body = response.read()
        result = loads(body)
        print(result)

usage = "usage: %prog"
parser = OptionParser("usage: %prog")
parser.add_option('-u', '--url', dest='url', metavar='URL',
                  help="The base URL to hit, default http://localhost:8000",
                  default="http://localhost:8000")
(options, args) = parser.parse_args()

try:
    list_projects(options.url)
except HTTPError as e:
    print("HTTPError {0}: {1}", e.code, e.reason)
    if e.code == 403 or e.code == 401:
        print("Attempting token refresh")
        req = Request(options.url + "/ftc/api/refresh-token", method='POST')
        with open('refresh.token', 'r') as fh:
            refresh = fh.read()
        data = urlencode({
            'refresh': refresh
        }).encode('ascii')
        with urlopen(req, data=data) as response:
            body = response.read()
            result = loads(body)
            if 'access' not in result:
                raise "No access token returned"
            with open('access.token', 'w') as access:
                access.write(result['access'])
        list_projects(options.url)
