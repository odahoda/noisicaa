#!/usr/bin/python3

import unittest

from . import db


class NodeDBTest(unittest.TestCase):
    def test_load_csound_nodes(self):
        node_db = db.NodeDB()
        node_db.load_csound_nodes()


if __name__ == '__main__':
    unittest.main()
