#!/usr/bin/python3

import unittest

from . import node_db


class NodeDBTest(unittest.TestCase):
    def test_load_csound_nodes(self):
        db = node_db.NodeDB()
        db.load_csound_nodes()


if __name__ == '__main__':
    unittest.main()
