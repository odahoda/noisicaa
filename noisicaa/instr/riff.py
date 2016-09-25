#!/usr/bin/python3

import os.path
import io
import logging
import sys
import struct

logger = logging.getLogger(__name__)

class Error(Exception):
    pass

class FormatError(Error):
    pass

class DataError(Error):
    pass


class RiffFile(object):
    def start_list(self, identifier, path):
        pass

    def end_list(self, identifier, path):
        pass

    def handle_chunk(self, identifier, path, size, fp):
        pass

    def parse(self, path):
        logger.info("Opening file %s", path)
        with open(path, 'rb') as fp:
            if os.path.getsize(path) < 8:
                raise DataError("File truncated")

            sig = fp.read(4)
            if sig != b'RIFF':
                raise FormatError("RIFF signature not found")

            size = struct.unpack('<L', fp.read(4))[0]
            logger.debug("0x%08x: Content size %r", 4, size)
            if size == os.path.getsize(path):
                logger.debug("Uncorrect content size (includes RIFF header)")
                size -= 8

            if size + 8 != os.path.getsize(path):
                raise DataError(
                    "File size mismatch (expected %d, got %d)"
                    % (size + 8, os.path.getsize(path)))

            self._parse_list(fp, [], 8, size + 8)

        return self

    def _parse_list(self, fp, path, offset, end_offset):
        list_identifier = fp.read(4)
        try:
            list_identifier = list_identifier.decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Malformed identifier %r" % list_identifier)
        logger.debug("0x%08x: List identifier %r", offset, list_identifier)
        offset += 4

        self.start_list(list_identifier, path)
        while offset < end_offset:
            identifier = fp.read(4)
            try:
                identifier = identifier.decode('ascii')
            except UnicodeDecodeError:
                raise FormatError("Malformed identifier %r" % identifier)
            logger.debug("0x%08x: Chunk identifier %r", offset, identifier)
            offset += 4

            chunksize = struct.unpack('<L', fp.read(4))[0]
            logger.debug("0x%08x: Chunk size: %d", offset, chunksize)
            offset += 4

            if identifier == 'LIST':
                self._parse_list(fp, path + [list_identifier], offset, offset + chunksize)
            else:
                self.handle_chunk(identifier, path + [list_identifier], chunksize, fp)
                fp.seek(offset + (chunksize + 1) & 0xfffffffe, io.SEEK_SET)

            if offset + chunksize == end_offset and chunksize & 1 == 1:
                logger.debug("Ignoring missing pad byte on last chunk.")
                offset = end_offset
            else:
                offset += (chunksize + 1) & 0xfffffffe
                if offset > end_offset:
                    raise FormatError("%d > %d" % (offset, end_offset))

        self.end_list(list_identifier, path)


if __name__ == '__main__':
    class DumpStructure(RiffFile):
        def start_list(self, identifier, path):
            print("BEGIN %s" % ' > '.join(path + [identifier]))

        def end_list(self, identifier, path):
            print("END   %s" % ' > '.join(path + [identifier]))

        def handle_chunk(self, identifier, path, size, fp):
            print(
                "CHUNK %s (%d bytes)" % (' > '.join(path + [identifier]), size))

    logger.setLevel(logging.DEBUG)
    DumpStructure().parse(sys.argv[1])
