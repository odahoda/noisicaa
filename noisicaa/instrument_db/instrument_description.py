#!/usr/bin/python3

import enum
import urllib.parse

class InstrumentDescription(object):
    def __init__(self, uri, display_name):
        self.uri = uri
        self.display_name = display_name


def parse_uri(uri):
    fmt, _, path, _, args, _ = urllib.parse.urlparse(uri)
    path = urllib.parse.unquote(path)
    if args:
        args = dict(urllib.parse.parse_qsl(args, strict_parsing=True))
    else:
        args = {}

    if fmt == 'sf2':
        return 'fluidsynth', {
            'soundfont_path': path,
            'bank': int(args['bank']),
            'preset': int(args['preset'])
        }

    elif fmt == 'sample':
        return 'sample_player', {
            'sample_path': path,
        }

    else:
        raise ValueError(fmt)
