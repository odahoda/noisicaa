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

import time

from noisidev import unittest
from . import libalsa


class AlsaSequencerTest(unittest.TestCase):
    @unittest.skip("Fails under virtualbox.")
    def test_list_clients(self):
        with libalsa.AlsaSequencer() as seq:
            for client_info in seq.list_clients():
                self.assertIsInstance(client_info, libalsa.ClientInfo)

    @unittest.skip("Fails under virtualbox.")
    def test_list_ports(self):
        with libalsa.AlsaSequencer() as seq:
            client_info = next(seq.list_clients())
            for port_info in seq.list_client_ports(client_info):
                self.assertIsInstance(port_info, libalsa.PortInfo)

    @unittest.skip("Fails under virtualbox.")
    def test_list_all_ports(self):
        with libalsa.AlsaSequencer() as seq:
            for port_info in seq.list_all_ports():
                self.assertIsInstance(port_info, libalsa.PortInfo)

    @unittest.skip("Can't assume presence of real MIDI input on system.")
    def test_connect(self):
        with libalsa.AlsaSequencer() as seq:
            port_info = next(
                p for p in seq.list_all_ports()
                if 'read' in p.capabilities and 'hardware' in p.types)
            seq.connect(port_info)
            time.sleep(10)
            seq.disconnect(port_info)
            with self.assertRaises(libalsa.APIError):
                seq.disconnect(port_info)

    # def test_get_event(self):
    #     with libalsa.AlsaSequencer() as seq:
    #         port_info = next(
    #             p for p in seq.list_all_ports()
    #             if 'read' in p.capabilities and 'hardware' in p.types)
    #         seq.connect(port_info)

    #         for _ in range(100):
    #             seq.get_event()
