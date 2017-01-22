#!/usr/bin/python3

import unittest

from . import event_set


class EventSetTest(unittest.TestCase):
    def test_foo(self):
        es = event_set.EventSet()


if __name__ == '__main__':
    unittest.main()
