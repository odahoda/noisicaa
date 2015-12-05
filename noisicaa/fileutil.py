#!/usr/bin/python3

import json
import hashlib
import email.message
import email.parser
import email.policy
import os.path
import struct

from . import logging

logger = logging.getLogger(__name__)


class Error(Exception):
    pass

class NotFoundError(Error):
    pass

class BadFileFormatError(Error):
    pass

class CorruptedFileError(Error):
    pass


class FileInfo(object):
    def __init__(self, version=None, filetype=None):
        self.version = version
        self.filetype = filetype
        self.content_type = None
        self.encoding = None


class File(object):
    MAGIC = b'NOISICAA\n'

    def __init__(self, path):
        super().__init__()

        self.path = path

    def write_json(self, obj, file_info, encoder=json.JSONEncoder):
        content = json.dumps(
            obj,
            ensure_ascii=False, indent='  ', sort_keys=True, cls=encoder)
        self.write_text(content, 'application/json', 'utf-8', file_info)

    def write_text(self, content, content_type, encoding, file_info):
        content = content.encode(encoding)

        policy = email.policy.compat32.clone(
            linesep='\n',
            max_line_length=0,
            cte_type='8bit',
            raise_on_defect=True)
        message = email.message.Message(policy)

        if file_info.version is not None:
            message.add_header('Version', str(file_info.version))
        if file_info.filetype is not None:
            message.add_header('File-Type', file_info.filetype)

        message.add_header('Checksum', hashlib.md5(content).hexdigest(),
                           type='md5')
        message.add_header('Content-Type', content_type,
                           charset=encoding)
        message.add_header('Content-Length', str(len(content)))

        with open(self.path, 'wb') as fp:
            fp.write(self.MAGIC)
            fp.write(message.as_bytes())
            fp.write(content)

    def read(self):
        if not os.path.exists(self.path):
            raise NotFoundError()

        with open(self.path, 'rb') as fp:
            magic = fp.read(len(self.MAGIC))
            if magic != self.MAGIC:
                raise BadFileFormatError("Not an noisicaä file")

            # email.parser's headersonly attribute doesn't seem to work the
            # way I would expect it.
            headers = b''
            while headers[-2:] != b'\n\n':
                b = fp.read(1)
                if not b:
                    break
                headers += b

            parser = email.parser.BytesParser()
            message = parser.parsebytes(headers)

            content = fp.read()

            if 'Checksum' in message:
                should_checksum = message['Checksum'].split(';')[0]
                checksum_type = message.get_param('type', None, 'Checksum')
                if checksum_type is None:
                    raise BadFileFormatError("Checksum type not specified")
                if checksum_type == 'md5':
                    have_checksum = hashlib.md5(content).hexdigest()
                else:
                    raise BadFileFormatError(
                        "Unsupported checksum type '%s'" % checksum_type)

                if have_checksum != should_checksum:
                    raise CorruptedFileError(
                        "Checksum mismatch (%s != %s)"
                        % (have_checksum, should_checksum))

            file_info = FileInfo()
            file_info.content_type = message.get_content_type()
            file_info.encoding = message.get_param('charset', 'ascii')
            if 'Version' in message:
                file_info.version = int(message['Version'])
            if 'File-Type' in message:
                file_info.filetype = message['File-Type']

            return file_info, content

    def read_json(self, decoder=json.JSONDecoder):
        file_info, content = self.read()
        if file_info.content_type != 'application/json':
            raise BadFileFormatError("Expected Content-Type application/json")
        return file_info, json.loads(content.decode(file_info.encoding),
                                     cls=decoder)


class LogFile(object):
    ENTRY_BEGIN = b'~B'
    ENTRY_END = b'~E'

    def __init__(self, path, mode):
        if mode not in ('a', 'w', 'r'):
            raise ValueError("Invalid mode %r" % mode)

        self.path = path
        self.mode = mode
        self._fp = open(self.path, mode + 'b')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        assert self._fp is not None, "LogFile already closed."
        self._fp.close()
        self._fp = None

    @property
    def closed(self):
        return self._fp is None

    def append(self, data, entry_type):
        assert self._fp is not None, "LogFile already closed."
        assert self.mode in ('a', 'w'), "LogFile not opened for writing."

        if not isinstance(data, bytes):
            raise TypeError("Expected bytes, got %s." % type(data).__name__)
        if not isinstance(entry_type, bytes):
            raise TypeError("Expected bytes, got %s." % type(entry_type).__name__)
        if len(entry_type) != 1:
            raise ValueError("entry_type must be a single byte.")

        data = data.replace(b'~', b'~~')

        self._fp.write(self.ENTRY_BEGIN)
        self._fp.write(entry_type)
        self._fp.write(struct.pack('>L', len(data)))
        self._fp.write(data)
        self._fp.write(self.ENTRY_END)
        self._fp.write(entry_type)
        self._fp.write(struct.pack('>L', len(data)))

    def read(self):
        assert self._fp is not None, "LogFile already closed."
        assert self.mode == 'r', "LogFile not opened for reading."

        entry_begin = self._fp.read(len(self.ENTRY_BEGIN))
        if not entry_begin:
            raise EOFError

        if entry_begin != self.ENTRY_BEGIN:
            raise CorruptedFileError('No entry begin marker found.')

        entry_type = self._fp.read(1)
        if len(entry_type) != 1:
            raise CorruptedFileError('Truncated entry.')

        length = self._fp.read(4)
        if len(length) != 4:
            raise CorruptedFileError('Truncated entry.')
        length, = struct.unpack('>L', length)

        data = self._fp.read(length)
        if len(data) != length:
            raise CorruptedFileError('Truncated entry.')

        data = data.replace(b'~~', b'~')

        entry_end = self._fp.read(len(self.ENTRY_END))
        if len(entry_end) != len(self.ENTRY_END):
            raise CorruptedFileError('Truncated entry.')
        if entry_end != self.ENTRY_END:
            raise CorruptedFileError('No entry end marker found.')

        entry_type_end = self._fp.read(1)
        if len(entry_type_end) != 1:
            raise CorruptedFileError('Truncated entry.')
        if entry_type_end != entry_type:
            raise CorruptedFileError(
                'Entry type mismatch (%r != %r).' % (entry_type_end, entry_type))

        length_end = self._fp.read(4)
        if len(length_end) != 4:
            raise CorruptedFileError('Truncated entry.')
        length_end, = struct.unpack('>L', length_end)
        if length_end != length:
            raise CorruptedFileError(
                'Length mismatch (%r != %r).' % (length_end, length))

        return data, entry_type

    def __iter__(self):
        while True:
            try:
                yield self.read()
            except EOFError:
                break

