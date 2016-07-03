#!/usr/bin/python3

import unittest

from . import sourcetest
from . import silence


class SilenceTest(sourcetest.SourceTest):
    def make_node(self):
        return silence.SilenceSource(self.loop)


if __name__ == '__main__':
    unittest.main()
