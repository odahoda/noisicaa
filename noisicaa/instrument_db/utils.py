# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import urllib.parse

from noisicaa import audioproc


class InvalidInstrumentURI(Exception):
    pass


def create_instrument_spec(uri: str) -> audioproc.InstrumentSpec:
    if not uri:
        raise InvalidInstrumentURI("Empty URI")

    fmt, _, path, _, query, _ = urllib.parse.urlparse(uri)
    if not path:
        raise InvalidInstrumentURI("Missing path")

    path = urllib.parse.unquote(path)

    if query:
        args = dict(urllib.parse.parse_qsl(query, strict_parsing=True))
    else:
        args = {}

    if fmt == 'sf2':
        instrument_spec = audioproc.InstrumentSpec(
            sf2=audioproc.SF2InstrumentSpec(
                path=path,
                bank=int(args.get('bank', 0)),
                preset=int(args.get('preset', 0))))

    elif fmt == 'sample':
        instrument_spec = audioproc.InstrumentSpec(
            sample=audioproc.SampleInstrumentSpec(
                path=path))

    else:
        raise InvalidInstrumentURI("Unknown scheme '%s'" % fmt)

    return instrument_spec
