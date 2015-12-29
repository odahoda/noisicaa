#!/usr/bin/python3

import unittest
from unittest import mock

from . import callbacks

class CallbackRegistryTest(unittest.TestCase):
    def test_callbacks(self):
        listener1 = mock.Mock()
        listener2 = mock.Mock()

        registry = callbacks.CallbackRegistry()
        lid1 = registry.add('foo', listener1)
        lid2 = registry.add('bar', listener2)

        # Nothing gets called.
        registry.callback('gnurz', 'arg0')
        self.assertEqual(listener1.call_args_list, [])
        self.assertEqual(listener2.call_args_list, [])

        # Only listener1 gets called.
        registry.callback('foo', 'arg1')
        self.assertEqual(listener1.call_args_list, [mock.call('arg1')])
        self.assertEqual(listener2.call_args_list, [])

        # listener1 is not called again.
        registry.remove(lid1)
        registry.callback('foo', 'arg2')
        self.assertEqual(listener1.call_args_list, [mock.call('arg1')])

        # Now listener2 gets called.
        registry.callback('bar', 'arg3')
        self.assertEqual(listener2.call_args_list, [mock.call('arg3')])

        # listener2 is not called again.
        registry.remove(lid2)
        registry.callback('bar', 'arg4')
        self.assertEqual(listener2.call_args_list, [mock.call('arg3')])


if __name__ == '__main__':
    unittest.main()
