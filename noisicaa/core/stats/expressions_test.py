#!/usr/bin/python3

import unittest

from . import expressions
from . import stats

class CompileExpressionTest(unittest.TestCase):
    def test_select(self):
        self.assertEqual(
            expressions.compile_expression('SELECT(name="foo")'),
            [('SELECT', stats.StatName(name='foo'))])

    def test_rate(self):
        self.assertEqual(
            expressions.compile_expression('SELECT(name="foo").RATE()'),
            [('SELECT', stats.StatName(name='foo')),
             ('RATE',)])


if __name__ == '__main__':
    unittest.main()
