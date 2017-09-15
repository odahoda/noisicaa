#!/usr/bin/python3

import enum
import urllib.parse

class Property(enum.Enum):
    # int
    BitsPerSample = 'bits-per-sample'

    # int
    NumChannels = 'num-channels'

    SampleFormat = 'sample-format'

    # int, samples per seconds
    SampleRate = 'sample-rate'

    # int
    NumSamples = 'num-samples'

    # float, in seconds
    Duration = 'duration'


class InstrumentDescription(object):
    def __init__(self, uri, path, display_name, properties):
        self.uri = uri
        self.path = path
        self.display_name = display_name
        self.properties = properties

    @property
    def format(self):
        return urllib.parse.urlparse(self.uri).scheme


def parse_uri(uri):
    fmt, _, path, _, args, _ = urllib.parse.urlparse(uri)
    path = urllib.parse.unquote(path)
    if args:
        args = dict(urllib.parse.parse_qsl(args, strict_parsing=True))
    else:
        args = {}

    if fmt == 'sf2':
        return 'builtin://fluidsynth', {
            'soundfont_path': path,
            'bank': int(args['bank']),
            'preset': int(args['preset'])
        }

    elif fmt == 'sample':
        return 'builtin://sample_player', {
            'sample_path': path,
        }

    else:
        raise ValueError(fmt)
