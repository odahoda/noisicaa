#!/usr/bin/python3

import socket
import threading
import time
import unittest

from . import ipc


class IPCTest(unittest.TestCase):
    def test_ping(self):
        with ipc.Server(name='test') as server:
            server.start()
            with ipc.Stub(server.address) as stub:
                stub.ping()
                stub.ping()
                stub.ping()

    def test_command(self):
        with ipc.Server(name='test') as server:
            server.start()
            with ipc.Stub(server.address) as stub:
                self.assertIsNone(stub.call('foo'))
                self.assertEqual(stub.call('foo', b'12345'), b'12345')
                self.assertIsNone(stub.call('foo'))

if __name__ == '__main__':
    import logging
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
