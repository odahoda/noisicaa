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

# TODO: pylint-unclean

import logging
import struct

from . import riff

logger = logging.getLogger(__name__)

class Error(riff.Error):
    pass

class FormatError(Error):
    pass


class WaveFile(riff.RiffFile):
    def __init__(self):
        super().__init__()
        self._seen = set()

        self.data_format = None
        self.channels = None
        self.sample_rate = None
        self.bits_per_sample = None

        self._num_samples = None
        self._bytes_per_sample = None
        self._data_length = None

    @property
    def num_samples(self):
        if self._num_samples is not None:
            return self._num_samples

        if self._data_length is not None and self._bytes_per_sample is not None:
            return self._data_length // self._bytes_per_sample

        return None

    def start_list(self, identifier, path):
        if path == [] and identifier != 'WAVE':
            raise FormatError("Note a WAVE file")

        if identifier in ('INFO', 'pdta') and path == []:
            if identifier in self._seen:
                raise FormatError("Duplicate %s chunk" % identifier)
            self._seen.add(identifier)

    def handle_chunk(self, identifier, path, size, fp):
        logger.debug(
            "CHUNK %s (%d bytes)", ' > '.join(path + [identifier]), size)
        handler_name = 'handle_' + '_'.join(id.strip() for id in path + [identifier])
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(size, fp)

    def handle_WAVE_fmt(self, size, fp):
        if 'WAVE/fmt' in self._seen:
            raise FormatError("Duplicate fmt chunk")
        self._seen = 'WAVE/fmt'

        if size not in (16, 18, 40):
            raise FormatError("Invalid fmt chunk size %d" % size)

        wFormatTag, nChannels, nSamplesPerSec, nAvgBytesPerSec, nBlockAlign, wBitsPerSample = (
            struct.unpack('<HHIIHH', fp.read(16)))

        if wFormatTag == 0x0001:
            self.data_format = 'pcm'
        elif wFormatTag == 0x0003:
            self.data_format = 'float'
        elif wFormatTag == 0x0006:
            self.data_format = 'a-law'
        elif wFormatTag == 0x0007:
            self.data_format = 'u-law'
        else:
            self.data_format == '0x%04X' % wFormatTag

        self.channels = nChannels
        self.sample_rate = nSamplesPerSec
        self.bits_per_sample = wBitsPerSample
        self._bytes_per_sample = nBlockAlign

        if size >= 18:
            cbSize, = struct.unpack('<H', fp.read(2))
            if cbSize == 22:
                wValidBitsPerSample, dwChannelMast, SubFormat = struct.unpack('<HI16s', fp.read(cbSize))

    def handle_WAVE_fact(self, size, fp):
        if 'WAVE/fact' in self._seen:
            raise FormatError("Duplicate fact chunk")
        self._seen = 'WAVE/fact'

        if size < 4:
            raise FormatError("Invalid fact chunk size %d" % size)

        dwSampleLength, = struct.unpack('<I', fp.read(4))
        self._num_samples = dwSampleLength

    def handle_WAVE_data(self, size, fp):
        if 'WAVE/data' in self._seen:
            raise FormatError("Duplicate data chunk")
        self._seen = 'WAVE/data'

        self._data_length = size
