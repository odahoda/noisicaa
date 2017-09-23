#!/usr/bin/python3

import unittest

from . import message


class BuildMessageTest(unittest.TestCase):
    def test_build_message(self):
        msg = message.build_message(
            {message.MessageKey.sheetId: '123'},
            message.MessageType.atom, b'abcd')
        self.assertEqual(len(msg.labelset.labels), 1)
        self.assertEqual(msg.labelset.labels[0].key, message.MessageKey.sheetId)
        self.assertEqual(msg.labelset.labels[0].value, '123')
        self.assertEqual(msg.type, message.MessageType.atom)
        self.assertEqual(msg.data, b'abcd')


if __name__ == '__main__':
    unittest.main()
