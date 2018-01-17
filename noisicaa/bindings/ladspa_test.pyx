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

import struct
import unittest

import numpy

from . cimport ladspa


class LadspaTest(unittest.TestCase):
    def test_foo(self):
        lib = ladspa.Library('/usr/lib/ladspa/sine.so')
        for desc in lib.descriptors:
            print(desc.id, desc.name, desc.label, desc.maker, desc.copyright)
            for port in desc.ports:
                print(port)


    def test_run_instance(self):
        lib = ladspa.Library('/usr/lib/ladspa/sine.so')
        desc = lib.get_descriptor('sine_fcac')
        cdef ladspa.Instance inst = desc.instantiate(44100)
        try:
            p1 = struct.pack('=f', 440.0)
            p2 = struct.pack('=f', 1.0)
            p3 = bytearray(400)

            inst.connect_port(desc.ports[0], <char*>p1)
            inst.connect_port(desc.ports[1], <char*>p2)
            inst.connect_port(desc.ports[2], <char*>p3)

            inst.activate()
            inst.run(100)
            print(p3)
            inst.run(100)
            print(p3)

            inst.deactivate()
        finally:
            inst.close()
