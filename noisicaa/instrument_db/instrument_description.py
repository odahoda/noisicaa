#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import enum
import urllib.parse
from typing import Callable

from noisicaa import node_db


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


def parse_uri(
        uri: str,
        get_node_description: Callable[[str], node_db.NodeDescription]) -> node_db.NodeDescription:
    fmt, _, path, _, args, _ = urllib.parse.urlparse(uri)
    path = urllib.parse.unquote(path)
    if args:
        args = dict(urllib.parse.parse_qsl(args, strict_parsing=True))
    else:
        args = {}

    if fmt == 'sf2':
        desc = get_node_description('builtin://fluidsynth')
        desc.fluidsynth.soundfont_path = path
        desc.fluidsynth.bank = int(args['bank'])
        desc.fluidsynth.preset = int(args['preset'])
        return desc

    elif fmt == 'sample':
        desc = get_node_description('builtin://sample_player')
        desc.sample_player.sample_path = path
        return desc

    else:
        raise ValueError(fmt)
