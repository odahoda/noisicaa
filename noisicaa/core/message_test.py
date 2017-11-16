#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from . import message


class BuildMessageTest(unittest.TestCase):
    def test_build_message(self):
        msg = message.build_message(
            {message.MessageKey.trackId: '123'},
            message.MessageType.atom, b'abcd')
        self.assertEqual(len(msg.labelset.labels), 1)
        self.assertEqual(msg.labelset.labels[0].key, message.MessageKey.trackId)
        self.assertEqual(msg.labelset.labels[0].value, '123')
        self.assertEqual(msg.type, message.MessageType.atom)
        self.assertEqual(msg.data, b'abcd')


if __name__ == '__main__':
    unittest.main()
