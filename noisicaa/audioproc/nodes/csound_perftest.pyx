#!/usr/bin/python3

from libc.stdint cimport uint8_t

import unittest
import textwrap

from noisidev import profutil

from noisicaa import node_db
from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 cimport urid
from ..vm cimport buffers
from .. import data
from . cimport csound


class CSoundPerfTest(unittest.TestCase):
    def test_basic(self):
        cdef:
            csound.CustomCSound node
            atom.AtomForge forge
            buffers.Buffer buf_in
            buffers.Buffer buf_out

        desc = node_db.NodeDescription(
            ports=[
                node_db.EventPortDescription(
                    name='in',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ],
            parameters=[
                node_db.TextParameterDescription(
                    name='orchestra',
                    display_name='Orchestra Code',
                    content_type='text/csound-orchestra',
                    default=textwrap.dedent("""\
                        instr 2
                            gaOut = 0
                        endin
                    """)),
                node_db.TextParameterDescription(
                    name='score',
                    display_name='Score',
                    content_type='text/csound-score',
                    default='i2 0 -1'),
            ],
        )

        node = csound.CustomCSound(id='test', description=desc)
        node.setup()
        try:
            buf_in = buffers.Buffer(buffers.AtomData(10240))
            buf_out = buffers.Buffer(buffers.FloatArray(256))
            node.connect_port('in', buf_in)
            node.connect_port('out', buf_out)

            forge = atom.AtomForge(urid.get_static_mapper())
            forge.set_buffer(<uint8_t*>buf_in.data, 10240)
            with forge.sequence():
                forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
                forge.write_midi_event(128, bytes([0x80, 60, 0]), 3)

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 256

            def loop():
                for _ in range(1000):
                    node.run(ctxt)

            profutil.profile(self.id(), loop)

        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()
