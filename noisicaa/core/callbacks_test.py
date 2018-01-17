#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

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
        registry.call('gnurz', 'arg0')
        self.assertEqual(listener1.call_args_list, [])
        self.assertEqual(listener2.call_args_list, [])

        # Only listener1 gets called.
        registry.call('foo', 'arg1')
        self.assertEqual(listener1.call_args_list, [mock.call('arg1')])
        self.assertEqual(listener2.call_args_list, [])

        # listener1 is not called again.
        lid1.remove()
        registry.call('foo', 'arg2')
        self.assertEqual(listener1.call_args_list, [mock.call('arg1')])

        # Now listener2 gets called.
        registry.call('bar', 'arg3')
        self.assertEqual(listener2.call_args_list, [mock.call('arg3')])

        # listener2 is not called again.
        lid2.remove()
        registry.call('bar', 'arg4')
        self.assertEqual(listener2.call_args_list, [mock.call('arg3')])


if __name__ == '__main__':
    unittest.main()
