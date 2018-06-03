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

from unittest import mock

from noisidev import unittest
from . import callbacks


class CallbackMapTest(unittest.TestCase):
    def test_callbacks(self):
        listener1 = mock.Mock()
        listener2 = mock.Mock()

        cbmap = callbacks.CallbackMap[str, str]()
        lid1 = cbmap.add('foo', listener1)
        lid2 = cbmap.add('bar', listener2)

        # Nothing gets called.
        cbmap.call('gnurz', 'arg0')
        self.assertEqual(listener1.call_args_list, [])
        self.assertEqual(listener2.call_args_list, [])

        # Only listener1 gets called.
        cbmap.call('foo', 'arg1')
        self.assertEqual(listener1.call_args_list, [mock.call('arg1')])
        self.assertEqual(listener2.call_args_list, [])

        # listener1 is not called again.
        lid1.remove()
        cbmap.call('foo', 'arg2')
        self.assertEqual(listener1.call_args_list, [mock.call('arg1')])

        # Now listener2 gets called.
        cbmap.call('bar', 'arg3')
        self.assertEqual(listener2.call_args_list, [mock.call('arg3')])

        # listener2 is not called again.
        lid2.remove()
        cbmap.call('bar', 'arg4')
        self.assertEqual(listener2.call_args_list, [mock.call('arg3')])
