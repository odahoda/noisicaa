#!/usr/bin/python3

import unittest

import capnp

from . import entity_capnp
from . import frame_data_capnp


class FrameDataTest(unittest.TestCase):
    def test_basic_properties(self):
        builder = frame_data_capnp.FrameData.new_message()
        builder.samplePos = 10000
        builder.frameSize = 512

        builder.init('entities', 2)

        e = builder.entities[0]
        e.id = '1234'
        e.type = entity_capnp.Entity.Type.atom
        e.size = 10240
        e.data = bytes(10240)

        e = builder.entities[1]
        e.id = '2345'
        e.type = entity_capnp.Entity.Type.audio
        e.size = 1024
        e.data = bytes(1024)

        buf = builder.to_bytes_packed()

        fd = frame_data_capnp.FrameData.from_bytes_packed(buf)
        self.assertEqual(fd.samplePos, 10000)
        self.assertEqual(fd.frameSize, 512)
        self.assertEqual(len(fd.entities), 2)
        e = fd.entities[0]
        self.assertEqual(e.id, '1234')
        self.assertEqual(e.type, entity_capnp.Entity.Type.atom)
        self.assertEqual(e.size, 10240)
        e = fd.entities[1]
        self.assertEqual(e.id, '2345')
        self.assertEqual(e.type, entity_capnp.Entity.Type.audio)
        self.assertEqual(e.size, 1024)
