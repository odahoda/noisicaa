#!/usr/bin/python3

import unittest
import os
import os.path
import struct

from noisicaa import constants
from noisicaa import node_db
from noisicaa.audioproc import data
from . cimport ladspa
from ..vm cimport buffers


class LadspaTest(unittest.TestCase):
    def test_foo(self):
        cdef:
            ladspa.Ladspa node
            buffers.Buffer buf_cutoff
            buffers.Buffer buf_in
            buffers.Buffer buf_out

        description = node_db.NodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='Input',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='Output',
                    direction=node_db.PortDirection.Output),
            ],
            parameters=[
                node_db.InternalParameterDescription(
                    name='library_path', value='/usr/lib/ladspa/filter.so'),
                node_db.InternalParameterDescription(
                    name='label', value='lpf'),
                node_db.FloatParameterDescription(
                    name='Cutoff Frequency (Hz)',
                    display_name='Cutoff Frequency',
                    default=440.0,
                    min=0.0,
                    max=22050.0),
            ])
        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 256

        buf_cutoff = buffers.Buffer(buffers.Float())
        buf_in = buffers.Buffer(buffers.FloatArray(256))
        buf_out = buffers.Buffer(buffers.FloatArray(256))

        buf_cutoff.set_bytes(struct.pack('=f', 400.0))

        node = ladspa.Ladspa(id='test', description=description)
        node.setup()
        try:
            node.connect_port('Cutoff Frequency (Hz)', buf_cutoff)
            node.connect_port('Input', buf_in)
            node.connect_port('Output', buf_out)
            node.run(ctxt)
        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()
