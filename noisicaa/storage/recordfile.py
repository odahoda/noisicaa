#!/usr/bin/python3

import contextlib
import logging
import hashlib
import os
import re

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


class RecordFile(object):
    def __init__(self, path, mode):
        self._path = path
        self._mode = mode

        if self._mode == MODE_CREATE:
            self._fp = open(self._path, 'wb')
            self._index = 0
        elif self._mode == MODE_READONLY:
            self._fp = open(self._path, 'rb')
            self._index = 0
        else:
            raise ValueError("Invalid mode %r" % self._mode)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        assert self._fp is not None, "Already closed."
        self._fp.close()
        self._fp = None

    @property
    def num_records(self):
        return self._index

    def _format_properties(self, properties):
        prop_str = ', '.join('%s=%s' % (key, value)
                             for key, value in sorted(properties.items()))
        return prop_str.encode('ascii')

    def _compute_checksum(self, data, properties):
        checksum = hashlib.md5()
        checksum.update(self._format_properties(properties))
        checksum.update(data)
        return 'md5:' + checksum.hexdigest()
        
    def append_record(self, data, **properties):
        assert isinstance(data, bytes), \
            "Expected bytes, got %s" % type(data).__name__
        assert self._fp is not None, "Already closed."

        for key, value in properties.items():
            assert _PROP_KEY_RE.match(key), "Invalid key %r." % key
            assert isinstance(value, str), \
                "Expected str, got %s" % type(value).__name__
            assert _PROP_VALUE_RE.match(value), "Invalid value %r." % value

        data = data.replace(b'#\\', b'#\\\\')
        data = data.replace(b'#~', b'#\\~')

        properties = dict(properties)
        properties['size'] = str(len(data))
        properties['index'] = str(self._index)
        properties['checksum'] = self._compute_checksum(data, properties)
        if len(data) > 0 and data[-1] != LF:
            properties['traillf'] = '1'
            traillf = True
        else:
            traillf = False

        self._fp.write(b'#~REC: ')
        self._fp.write(self._format_properties(properties))
        self._fp.write(b'\n')
        self._fp.write(data)
        if traillf:
            self._fp.write(b'\n')
        self._fp.flush()

        self._index += 1

    def read_record(self):
        assert self._fp is not None, "Already closed."
        assert self._mode in (MODE_READONLY,), "File not opened in read mode."

        header = self._fp.read(6)
        if len(header) == 0:
            raise EOFError

        if header != b'#~REC:':
            raise CorruptedFileError("Expected '#~REC:', found %r" % header)

        while header[-1] != LF:
            header += self._fp.read(1)

        properties = {}
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

        data = self._fp.read(size)
        if len(data) != size:
            raise CorruptedFileError(
                "Truncated data, %d bytes missing." % (size - len(data)))
            
        if self._compute_checksum(data, properties) != checksum:
            raise CorruptedFileError("Checksum mismatch.")

        data = data.replace(b'#\\\\', b'#\\')
        data = data.replace(b'#\\~', b'#~', )

        if traillf:
            c = self._fp.read(1)
            if len(c) != 1 or ord(c) != LF:
                raise CorruptedFileError(
                    "Expected %r, found %r." % (chr(LF), c))

        properties['index'] = index
        del properties['size']
        return data, properties
