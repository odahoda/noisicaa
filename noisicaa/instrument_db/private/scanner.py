#!/usr/bin/python3

import urllib.parse

class Scanner(object):
    def __init__(self):
        pass

    def make_uri(self, fmt, path, **kwargs):
        return urllib.parse.urlunparse((
            fmt,
            None,
            urllib.parse.quote(path),
            None,
            urllib.parse.urlencode(sorted((k, str(v)) for k, v in kwargs.items()), True),
            None))

    def scan(self):
        raise NotImplementedError

