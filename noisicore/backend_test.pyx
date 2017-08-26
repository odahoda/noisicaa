from libcpp.memory cimport unique_ptr

from .buffers cimport *
from .status cimport *
from .vm cimport *
from .backend cimport *
from .host_data cimport *

import unittest


class TestPortAudioBackend(unittest.TestCase):
    def test_foo(self):
        cdef Status status
        cdef float samples[128]

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef unique_ptr[VM] vm
        vm.reset(new VM(host_data.get()))

        cdef unique_ptr[Backend] beptr
        beptr.reset(Backend.create(b"null"))

        cdef Backend* be = beptr.get()
        status = be.setup(vm.get())
        try:
            self.assertFalse(status.is_error(), status.message())

            for _ in range(100):
                status = be.begin_block()
                self.assertFalse(status.is_error(), status.message())

                for i in range(128):
                    samples[i] = i / 128.0
                status = be.output(b"left", <BufferPtr>samples)
                self.assertFalse(status.is_error(), status.message())
                status = be.output(b"right", <BufferPtr>samples)
                self.assertFalse(status.is_error(), status.message())

                status = be.end_block()
                self.assertFalse(status.is_error(), status.message())

        finally:
            be.cleanup()
