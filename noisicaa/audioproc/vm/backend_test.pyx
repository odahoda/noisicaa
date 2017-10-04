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

from libcpp.memory cimport unique_ptr

from noisicaa.core.status cimport *
from .buffers cimport *
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

        cdef PyBlockContext ctxt = PyBlockContext()
        for _ in range(100):
            check(be.begin_block(ctxt.get()))

            for i in range(128):
                samples[i] = i / 128.0
            check(be.output(ctxt.get(), b"left", <BufferPtr>samples))
            check(be.output(ctxt.get(), b"right", <BufferPtr>samples))

            check(be.end_block(ctxt.get()))

        be.cleanup()
