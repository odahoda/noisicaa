#!/usr/bin/python3

import time
import unittest

from . import libalsa

class AlsaSequencerTest(unittest.TestCase):
    def test_list_clients(self):
        with libalsa.AlsaSequencer() as seq:
            for client_info in seq.list_clients():
                self.assertIsInstance(client_info, libalsa.ClientInfo)

    def test_list_ports(self):
        with libalsa.AlsaSequencer() as seq:
            client_info = next(seq.list_clients())
            for port_info in seq.list_client_ports(client_info):
                self.assertIsInstance(port_info, libalsa.PortInfo)

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


if __name__ == '__main__':
    unittest.main()
