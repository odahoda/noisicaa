#!/usr/bin/python3

import unittest

from . import sourcetest
from . import whitenoise


class WhiteNoiseTest(sourcetest.SourceTest):
    def make_node(self):
        return whitenoise.WhiteNoiseSource()


if __name__ == '__main__':
    unittest.main()
