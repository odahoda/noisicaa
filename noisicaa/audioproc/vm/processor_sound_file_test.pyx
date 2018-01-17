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

from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

import os
import os.path
import sys
import unittest

from noisicaa import constants
from noisicaa.core.status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *
from .message_queue cimport *

class TestProcessorSoundFile(unittest.TestCase):
    def test_sound_file(self):
        cdef Status status

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.get(), b'sound_file')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())
        cdef Processor* processor = processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'out:left', PortType.audio, PortDirection.Output)
        spec.get().add_port(b'out:right', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(
            b'sound_file_path',
            os.fsencode(os.path.join(constants.ROOT, '..', 'testdata', 'snare.wav'))))

        check(processor.setup(spec.release()))

        cdef float outleftbuf[128]
        cdef float outrightbuf[128]

        check(processor.connect_port(0, <BufferPtr>outleftbuf))
        check(processor.connect_port(1, <BufferPtr>outrightbuf))

        for i in range(128):
            outleftbuf[i] = 0.0
            outrightbuf[i] = 0.0

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.block_size = 128

        cdef Message* msg
        done = False
        while not done:
            check(processor.run(ctxt.get(), NULL))  # TODO: pass time_mapper

            msg = ctxt.get().out_messages.get().first()
            while not ctxt.get().out_messages.get().is_end(msg):
                if msg.type == MessageType.SOUND_FILE_COMPLETE:
                    done = True
                msg = ctxt.get().out_messages.get().next(msg)

        self.assertTrue(any(v != 0.0 for v in outleftbuf))
        self.assertTrue(any(v != 0.0 for v in outrightbuf))

        processor.cleanup()
