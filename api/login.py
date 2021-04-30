#!/usr/bin/env python3
from getpass import getpass
from json import loads
from optparse import OptionParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen

usage = "usage: %prog -s SETTINGS | --settings=SETTINGS"
parser = OptionParser("usage: %prog USERNAME [PASSWORD]")
parser.add_option('-u', '--url', dest='url', metavar='URL',
                  help="The base URL to hit, default http://localhost:8000",
                  default="http://localhost:8000")
(options, args) = parser.parse_args()
la = len(args)
if la == 0:
    parser.error("a USERNAME is required")
if 2 < la:
    parser.error("Maximum two positional arguments are required (USERNAME and PASSWORD)")

username = args[0]
password = la == 2 and args[1] or getpass()

req = Request(options.url + "/ftc/api/get-token", method='POST')

data = urlencode({
    'username': username,
    'password': password,
}).encode('ascii')

with urlopen(req, data=data) as response:
    #TODO: urlopen raises an HTTP Error if not-OK response is returned.
    if response.status != 200:
        raise "Token acquisition failed with status {0}".format(response.status)
    body = response.read()
    result = loads(body)
    if 'refresh' not in result:
        raise "No refresh token returned"
    with open('refresh.token', 'w') as access:
        access.write(result['refresh'])
    if 'access' in result:
        with open('access.token', 'w') as access:
            access.write(result['access'])
    else:
        print("Warning: no access token returned (but that's probably OK)")
