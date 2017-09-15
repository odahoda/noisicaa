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

        cdef BackendSettings backend_settings

        cdef StatusOr[Backend*] stor_backend = Backend.create(b"null", backend_settings)
        check(stor_backend)

        cdef unique_ptr[Backend] backend_ptr
        backend_ptr.reset(stor_backend.result())

        cdef Backend* be = backend_ptr.get()
        check(be.setup(vm.get()))

        cdef BlockContext ctxt
        for _ in range(100):
            check(be.begin_block(&ctxt))

            for i in range(128):
                samples[i] = i / 128.0
            check(be.output(b"left", <BufferPtr>samples))
            check(be.output(b"right", <BufferPtr>samples))

            check(be.end_block())

        be.cleanup()
