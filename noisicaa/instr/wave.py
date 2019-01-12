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
import struct
from typing import Set, List, IO

from . import riff

logger = logging.getLogger(__name__)

class Error(riff.Error):
    pass

class FormatError(Error):
    pass


class WaveFile(riff.RiffFile):
    def __init__(self) -> None:
        super().__init__()

        self.data_format = None  # type: str
        self.channels = None  # type: int
        self.sample_rate = None  # type: int
        self.bits_per_sample = None  # type: int

        self.__seen = set()  # type: Set[str]
        self.__num_samples = None  # type: int
        self.__bytes_per_sample = None  # type: int
        self.__data_length = None  # type: int

    @property
    def num_samples(self) -> int:
        if self.__num_samples is not None:
            return self.__num_samples

        if self.__data_length is not None and self.__bytes_per_sample is not None:
            return self.__data_length // self.__bytes_per_sample

        return None

    def start_list(self, identifier: str, path: List[str]) -> None:
        if path == [] and identifier != 'WAVE':
            raise FormatError("Note a WAVE file")

        if identifier in ('INFO', 'pdta') and path == []:
            if identifier in self.__seen:
                raise FormatError("Duplicate %s chunk" % identifier)
            self.__seen.add(identifier)

    def handle_chunk(self, identifier: str, path: List[str], size: int, fp: IO) -> None:
        logger.debug(
            "CHUNK %s (%d bytes)", ' > '.join(path + [identifier]), size)
        handler_name = 'handle_' + '_'.join(id.strip() for id in path + [identifier])
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(size, fp)  # pylint: disable=not-callable

    def handle_WAVE_fmt(self, size: int, fp: IO) -> None:
        if 'WAVE/fmt' in self.__seen:
            raise FormatError("Duplicate fmt chunk")
        self.__seen.add('WAVE/fmt')

        if size not in (16, 18, 40):
            raise FormatError("Invalid fmt chunk size %d" % size)

        # pylint: disable=unused-variable
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
            self.data_format = '0x%04X' % wFormatTag

        self.channels = nChannels
        self.sample_rate = nSamplesPerSec
        self.bits_per_sample = wBitsPerSample
        self.__bytes_per_sample = nBlockAlign

        if size >= 18:
            cbSize, = struct.unpack('<H', fp.read(2))
            if cbSize == 22:
                # pylint: disable=unused-variable
                wValidBitsPerSample, dwChannelMast, SubFormat = struct.unpack(
                    '<HI16s', fp.read(cbSize))

    def handle_WAVE_fact(self, size: int, fp: IO) -> None:
        if 'WAVE/fact' in self.__seen:
            raise FormatError("Duplicate fact chunk")
        self.__seen.add('WAVE/fact')

        if size < 4:
            raise FormatError("Invalid fact chunk size %d" % size)

        dwSampleLength, = struct.unpack('<I', fp.read(4))
        self.__num_samples = dwSampleLength

    def handle_WAVE_data(self, size: int, fp: IO) -> None:
        if 'WAVE/data' in self.__seen:
            raise FormatError("Duplicate data chunk")
        self.__seen.add('WAVE/data')

        self.__data_length = size
