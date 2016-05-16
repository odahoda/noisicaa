#!/usr/bin/python3

import unittest

from . import ipc


class IPCTest(unittest.TestCase):
    def test_simple(self):
        pass


if __name__ == '__main__':
    import logging
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
