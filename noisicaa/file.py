#!/usr/bin/python3

import json
import hashlib
import email.message
import email.parser
import email.policy
import os.path

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
