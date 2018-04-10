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

import logging
import struct
from typing import List, Set, Tuple, IO  # pylint: disable=unused-import

from . import riff

logger = logging.getLogger(__name__)

class Error(riff.Error):
    pass

class FormatError(Error):
    pass


class Preset(object):
    def __init__(
            self,
            name: str,
            preset: int,
            bank: int,
            bag_index: int,
            library: int,
            genre: int,
            morphology: int
    ) -> None:
        self.name = name
        self.preset = preset
        self.bank = bank
        self.bag_index = bag_index
        self.library = library
        self.genre = genre
        self.morphology = morphology

    def __str__(self) -> str:
        return '%s (preset=%d, bank=%d)' % (self.name, self.preset, self.bank)
    __repr__ = __str__


class Instrument(object):
    def __init__(self, name: str, bag_index: int) -> None:
        self.name = name
        self.bag_index = bag_index

    def __str__(self) -> str:
        return '%s' % self.name
    __repr__ = __str__


class SoundFont(riff.RiffFile):
    def __init__(self) -> None:
        super().__init__()
        self.__seen = set()  # type: Set[str]

        self.file_version = None  # type: Tuple[int, int]
        self.sound_engine = 'EMU8000'  # type: str
        self.bank_name = None  # type: str
        self.rom_wavetable = None  # type: str
        self.rom_version = None  # type: Tuple[int, int]
        self.creation_date = None  # type: str
        self.creator = None  # type: str
        self.product = None  # type: str
        self.copyright = None  # type: str
        self.comments = None  # type: str
        self.software = None  # type: str

        self.presets = []  # type: List[Preset]
        self.instruments = []  # type: List[Instrument]

    def start_list(self, identifier: str, path: List[str]) -> None:
        if identifier in ('INFO', 'pdta') and path == []:
            if identifier in self.__seen:
                raise FormatError("Duplicate %s chunk" % identifier)
            self.__seen.add(identifier)

    def handle_chunk(self, identifier: str, path: List[str], size: int, fp: IO) -> None:
        logger.debug(
            "CHUNK %s (%d bytes)", ' > '.join(path + [identifier]), size)
        handler_name = 'handle_' + '_'.join(path + [identifier])
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(size, fp)  # pylint: disable=not-callable

    def handle_sfbk_INFO_ifil(self, size: int, fp: IO) -> None:
        if size != 4:
            raise FormatError("Invalid ifil chunk size %d" % size)
        major, minor = struct.unpack('<HH', fp.read(size))
        self.file_version = (major, minor)

    def handle_sfbk_INFO_isng(self, size: int, fp: IO) -> None:
        try:
            self.sound_engine = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in isng chunk")

    def handle_sfbk_INFO_INAM(self, size: int, fp: IO) -> None:
        try:
            self.bank_name = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in INAM chunk")

    def handle_sfbk_INFO_irom(self, size: int, fp: IO) -> None:
        try:
            self.rom_wavetable = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in irom chunk")

    def handle_sfbk_INFO_iver(self, size: int, fp: IO) -> None:
        if size != 4:
            raise FormatError("Invalid iver chunk size %d" % size)
        major, minor = struct.unpack('<HH', fp.read(size))
        self.rom_version = (major, minor)

    def handle_sfbk_INFO_ICRD(self, size: int, fp: IO) -> None:
        try:
            self.creation_date = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ICRD chunk")

    def handle_sfbk_INFO_IENG(self, size: int, fp: IO) -> None:
        try:
            self.creator = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in IENG chunk")

    def handle_sfbk_INFO_IPRD(self, size: int, fp: IO) -> None:
        try:
            self.product = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in IPRD chunk")

    def handle_sfbk_INFO_ICOP(self, size: int, fp: IO) -> None:
        try:
            self.copyright = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ICOP chunk")

    def handle_sfbk_INFO_ICMT(self, size: int, fp: IO) -> None:
        try:
            self.comments = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ICMT chunk")

    def handle_sfbk_INFO_ISFT(self, size: int, fp: IO) -> None:
        try:
            self.software = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ISFT chunk")

    def handle_sfbk_pdta_phdr(self, size: int, fp: IO) -> None:
        if size % 38 != 0 or size < 76:
            raise FormatError("Invalid phdr chunk size %d" % size)

        for _ in range(size // 38):
            name, preset, bank, bag_index, library, genre, morphology = (
                struct.unpack('<20sHHHLLL', fp.read(38)))
            try:
                name = name.rstrip(b'\0').decode('ascii')
            except UnicodeDecodeError:
                raise FormatError("Non-ASCII characters in phdr chunk")

            if name not in ("", "EOP"):
                self.presets.append(Preset(name, preset, bank, bag_index,
                                           library, genre, morphology))

    def handle_sfbk_pdta_inst(self, size: int, fp: IO) -> None:
        if size % 22 != 0 or size < 44:
            raise FormatError("Invalid inst chunk size %d" % size)

        for _ in range(size // 22):
            name, bag_index = (
                struct.unpack('<20sH', fp.read(22)))
            try:
                name = name.rstrip(b'\0').decode('ascii')
            except UnicodeDecodeError:
                raise FormatError("Non-ASCII characters in inst chunk")

            if name not in ("", "EOI"):
                self.instruments.append(Instrument(name, bag_index))
