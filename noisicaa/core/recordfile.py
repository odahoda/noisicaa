#!/usr/bin/python3

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

import logging
import hashlib
import re
from typing import Any, Dict, Tuple, Union

logger = logging.getLogger(__name__)


_PROP_KEY_RE = re.compile(r'[a-zAZ0-9]+$')
_PROP_VALUE_RE = re.compile(r'[-_./+a-zAZ0-9]+$')

MODE_READONLY = 'r'
MODE_CREATE = 'c'
MODE_APPEND = 'a'

LF = ord(b'\n')


class Error(Exception):
    pass

class CorruptedFileError(Error):
    pass


Properties = Dict[str, str]


class RecordFile(object):
    def __init__(self, path: str, mode: str) -> None:
        self.__path = path
        self.__mode = mode

        if self.__mode == MODE_CREATE:
            self.__fp = open(self.__path, 'wb')
            self.__index = 0
        elif self.__mode == MODE_READONLY:
            self.__fp = open(self.__path, 'rb')
            self.__index = 0
        else:
            raise ValueError("Invalid mode %r" % self.__mode)

    def __enter__(self) -> 'RecordFile':
        return self

    def __exit__(self, *args: Any) -> bool:
        self.close()
        return False

    def close(self) -> None:
        assert self.__fp is not None, "Already closed."
        self.__fp.close()
        self.__fp = None

    @property
    def num_records(self) -> int:
        return self.__index

    def __format_properties(self, properties: Properties) -> bytes:
        prop_str = ', '.join('%s=%s' % (key, value)
                             for key, value in sorted(properties.items()))
        return prop_str.encode('ascii')

    def __compute_checksum(self, data: bytes, properties: Properties) -> str:
        checksum = hashlib.md5()
        checksum.update(self.__format_properties(properties))
        checksum.update(data)
        return 'md5:' + checksum.hexdigest()

    def append_record(self, data: bytes, **properties: str) -> None:
        assert isinstance(data, bytes), \
            "Expected bytes, got %s" % type(data).__name__
        assert self.__fp is not None, "Already closed."

        for key, value in properties.items():
            assert _PROP_KEY_RE.match(key), "Invalid key %r." % key
            assert isinstance(value, str), \
                "Expected str, got %s" % type(value).__name__
            assert _PROP_VALUE_RE.match(value), "Invalid value %r." % value

        data = data.replace(b'#\\', b'#\\\\')
        data = data.replace(b'#~', b'#\\~')

        properties = dict(properties)
        properties['size'] = str(len(data))
        properties['index'] = str(self.__index)
        properties['checksum'] = self.__compute_checksum(data, properties)
        if len(data) > 0 and data[-1] != LF:
            properties['traillf'] = '1'
            traillf = True
        else:
            traillf = False

        self.__fp.write(b'#~REC: ')
        self.__fp.write(self.__format_properties(properties))
        self.__fp.write(b'\n')
        self.__fp.write(data)
        if traillf:
            self.__fp.write(b'\n')
        self.__fp.flush()

        self.__index += 1

    def read_record(self) -> Tuple[bytes, Dict[str, Union[str, int]]]:
        assert self.__fp is not None, "Already closed."
        assert self.__mode in (MODE_READONLY,), "File not opened in read mode."

        header = self.__fp.read(6)
        if len(header) == 0:
            raise EOFError

        if header != b'#~REC:':
            raise CorruptedFileError("Expected '#~REC:', found %r" % header)

        while header[-1] != LF:
            header += self.__fp.read(1)

        properties = {}  # Properties
        for part in header[6:-1].decode('ascii').split(','):
            key, value = part.split('=', 1)
            properties[key.strip()] = value.strip()

        for propname in ('size', 'index', 'checksum'):
            if propname not in properties:
                raise CorruptedFileError("Missing property '%s'." % propname)

        size = int(properties['size'])
        checksum = properties['checksum']
        index = int(properties['index'])

        if 'traillf' in properties:
            traillf = (properties['traillf'] == '1')
            del properties['traillf']
        else:
            traillf = False

        del properties['checksum']

        data = self.__fp.read(size)
        if len(data) != size:
            raise CorruptedFileError(
                "Truncated data, %d bytes missing." % (size - len(data)))

        if self.__compute_checksum(data, properties) != checksum:
            raise CorruptedFileError("Checksum mismatch.")

        data = data.replace(b'#\\\\', b'#\\')
        data = data.replace(b'#\\~', b'#~', )

        if traillf:
            c = self.__fp.read(1)
            if len(c) != 1 or ord(c) != LF:
                raise CorruptedFileError(
                    "Expected %r, found %r." % (chr(LF), c))

        tweaked_properties = {}  # type: Dict[str, Union[str, int]]
        tweaked_properties.update(properties)
        tweaked_properties['index'] = index
        del tweaked_properties['size']

        return data, tweaked_properties
