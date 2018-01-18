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

import sys

from libc.stdint cimport uint8_t
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

from noisidev import unittest
from noisicaa.core.status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *
from .message_queue cimport *


class TestProcessorTrackMixer(unittest.TestCase):
    def test_track_mixer(self):
        cdef Status status

        cdef PyHostData host_data = PyHostData()
        host_data.setup()

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.ptr(), b'track_mixer')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())

        cdef Processor* processor = processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'in:left', PortType.audio, PortDirection.Input)
        spec.get().add_port(b'in:right', PortType.audio, PortDirection.Input)
        spec.get().add_port(b'out:left', PortType.audio, PortDirection.Output)
        spec.get().add_port(b'out:right', PortType.audio, PortDirection.Output)
        spec.get().add_port(b'gain', PortType.kRateControl, PortDirection.Input)
        spec.get().add_port(b'muted', PortType.kRateControl, PortDirection.Input)
        spec.get().add_port(b'pan', PortType.kRateControl, PortDirection.Input)

        check(processor.setup(spec.release()))

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.block_size = 128

        cdef float inleftbuf[128]
        cdef float inrightbuf[128]
        cdef float outleftbuf[128]
        cdef float outrightbuf[128]
        cdef float gain
        cdef float muted
        cdef float pan

        check(processor.connect_port(0, <BufferPtr>inleftbuf))
        check(processor.connect_port(1, <BufferPtr>inrightbuf))
        check(processor.connect_port(2, <BufferPtr>outleftbuf))
        check(processor.connect_port(3, <BufferPtr>outrightbuf))
        check(processor.connect_port(4, <BufferPtr>&gain))
        check(processor.connect_port(5, <BufferPtr>&muted))
        check(processor.connect_port(6, <BufferPtr>&pan))

        for i in range(128):
            inleftbuf[i] = 1.0
            inrightbuf[i] = -1.0
            outleftbuf[i] = 0.0
            outrightbuf[i] = 0.0
        gain = 0.0
        muted = 0.0
        pan = 0.0

        check(processor.run(ctxt.get(), NULL))  # TODO: pass time_mapper
        self.assertTrue(any(v != 0.0 for v in outleftbuf))
        self.assertTrue(any(v != 0.0 for v in outrightbuf))

        muted = 1.0
        check(processor.run(ctxt.get(), NULL))  # TODO: pass time_mapper
        self.assertTrue(any(v == 0.0 for v in outleftbuf))
        self.assertTrue(any(v == 0.0 for v in outrightbuf))

        processor.cleanup()
