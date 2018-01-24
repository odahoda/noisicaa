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

from . import riff

logger = logging.getLogger(__name__)

class Error(riff.Error):
    pass

class FormatError(Error):
    pass


class Preset(object):
    def __init__(
            self, name, preset, bank, bag_index, library, genre, morphology):
        self.name = name
        self.preset = preset
        self.bank = bank
        self.bag_index = bag_index
        self.library = library
        self.genre = genre
        self.morphology = morphology

    def __str__(self):
        return '%s (preset=%d, bank=%d)' % (self.name, self.preset, self.bank)
    __repr__ = __str__


class Instrument(object):
    def __init__(
            self, name, bag_index):
        self.name = name
        self.bag_index = bag_index

    def __str__(self):
        return '%s' % self.name
    __repr__ = __str__


class SoundFont(riff.RiffFile):
    def __init__(self):
        super().__init__()
        self._seen = set()

        self.file_version = None
        self.sound_engine = 'EMU8000'
        self.bank_name = None
        self.rom_wavetable = None
        self.rom_version = None
        self.creation_date = None
        self.creator = None
        self.product = None
        self.copyright = None
        self.comments = None
        self.software = None

        self.presets = []
        self.instruments = []

    def start_list(self, identifier, path):
        if identifier in ('INFO', 'pdta') and path == []:
            if identifier in self._seen:
                raise FormatError("Duplicate %s chunk" % identifier)
            self._seen.add(identifier)

    def handle_chunk(self, identifier, path, size, fp):
        logger.debug(
            "CHUNK %s (%d bytes)", ' > '.join(path + [identifier]), size)
        handler_name = 'handle_' + '_'.join(path + [identifier])
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(size, fp)  # pylint: disable=not-callable

    def handle_sfbk_INFO_ifil(self, size, fp):
        if size != 4:
            raise FormatError("Invalid ifil chunk size %d" % size)
        major, minor = struct.unpack('<HH', fp.read(size))
        self.file_version = (major, minor)

    def handle_sfbk_INFO_isng(self, size, fp):
        try:
            self.sound_engine = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in isng chunk")

    def handle_sfbk_INFO_INAM(self, size, fp):
        try:
            self.bank_name = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in INAM chunk")

    def handle_sfbk_INFO_irom(self, size, fp):
        try:
            self.rom_wavetable = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in irom chunk")

    def handle_sfbk_INFO_iver(self, size, fp):
        if size != 4:
            raise FormatError("Invalid iver chunk size %d" % size)
        major, minor = struct.unpack('<HH', fp.read(size))
        self.rom_version = (major, minor)

    def handle_sfbk_INFO_ICRD(self, size, fp):
        try:
            self.creation_date = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ICRD chunk")

    def handle_sfbk_INFO_IENG(self, size, fp):
        try:
            self.creator = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in IENG chunk")

    def handle_sfbk_INFO_IPRD(self, size, fp):
        try:
            self.product = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in IPRD chunk")

    def handle_sfbk_INFO_ICOP(self, size, fp):
        try:
            self.copyright = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ICOP chunk")

    def handle_sfbk_INFO_ICMT(self, size, fp):
        try:
            self.comments = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ICMT chunk")

    def handle_sfbk_INFO_ISFT(self, size, fp):
        try:
            self.software = fp.read(size).rstrip(b'\0').decode('ascii')
        except UnicodeDecodeError:
            raise FormatError("Non-ASCII characters in ISFT chunk")

    def handle_sfbk_pdta_phdr(self, size, fp):
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

    def handle_sfbk_pdta_inst(self, size, fp):
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
