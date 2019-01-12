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

from noisidev import unittest
from noisicaa.bindings import sratom
from . import atom
from . import urid_mapper

logger = logging.getLogger(__name__)


class AtomForgeTest(unittest.TestCase):
    def setUp(self):
        self.mapper = urid_mapper.PyDynamicURIDMapper()

    def test_sequence(self):
        buf = bytearray(1024)

        forge = atom.AtomForge(self.mapper)
        forge.set_buffer(buf, 1024)

        with forge.sequence():
            forge.write_midi_event(0, b'abc', 3)
            forge.write_midi_event(1, b'abc', 3)

        logger.info(sratom.atom_to_turtle(self.mapper, buf))

    def test_object(self):

        forge = atom.AtomForge(self.mapper)

        buf = bytearray(1024)
        forge.set_buffer(buf, 1024)

        with forge.object(self.mapper.map('http://example.org/object')):
            forge.write_key(self.mapper.map('http://example.org/object#k1'))
            forge.write_string('foo')
            forge.write_key(self.mapper.map('http://example.org/object#k2'))
            forge.write_int(1234)
            forge.write_key(self.mapper.map('http://example.org/object#k3'))
            forge.write_double(13.78)
            forge.write_key(self.mapper.map('http://example.org/object#k4'))
            forge.write_bool(True)

        logger.info(sratom.atom_to_turtle(self.mapper, buf))

    # def test_build_midi_atom(self):
    #     buf = atom.AtomForge.build_midi_atom(b'123')

    #     a = atom.wrap_atom(urid.static_mapper, buf)
    #     self.assertIsInstance(a, atom.MidiEvent)


class AtomTest(unittest.TestCase):
    def setUp(self):
        self.mapper = urid_mapper.PyDynamicURIDMapper()

    def test_as_object(self):
        buf = (
            b'8\x00\x00\x00n\x00\x00\x00\xe8\x03\x00\x00\x00\x00\x00\x00}\x00\x00\x00\x00'
            b'\x00\x00\x00 \x00\x00\x00t\x00\x00\x00\x04\x00\x00\x00k\x00\x00\x00\x02\x00'
            b'\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00j\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00')
        o = atom.wrap_atom(self.mapper, buf)
        self.assertEqual(
            o.as_object,
            {'http://noisicaa.odahoda.de/lv2/core#portRMS': (2, 0.0)})

    # def test_sequence(self):
    #     buf = bytearray(1024)
    #     forge = atom.AtomForge(self.mapper)
    #     forge.set_buffer(buf, 1024)

    #     with forge.sequence():
    #         forge.write_midi_event(0, b'abc', 3)
    #         forge.write_midi_event(1, b'abc', 3)

    #     seq = atom.wrap_atom(self.mapper, buf)
    #     self.assertIsInstance(seq, atom.Sequence)
    #     logger.info(str(seq))
