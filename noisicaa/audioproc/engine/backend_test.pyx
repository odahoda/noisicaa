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

from libcpp.memory cimport unique_ptr

from noisidev import unittest
from noisidev cimport unittest_engine_mixins
from noisicaa.core.status cimport check, StatusOr
from .buffers cimport BufferPtr
from .realm cimport Realm
from .backend cimport Backend, BackendSettings
from .block_context cimport PyBlockContext


cdef class BackendTestMixin(unittest_engine_mixins.HostSystemMixin):
    def test_foo(self):
        cdef unique_ptr[Realm] realm
        realm.reset(new Realm(b"root", self.host_system.get(), NULL))

        cdef BackendSettings backend_settings
        cdef StatusOr[Backend*] stor_backend = Backend.create(
            self.host_system.get(), b"null", backend_settings)
        check(stor_backend)

        cdef unique_ptr[Backend] backend_ptr
        backend_ptr.reset(stor_backend.result())

        cdef Backend* be = backend_ptr.get()
        check(be.setup(realm.get()))

        buf = bytearray(sizeof(float) * self.host_system.block_size)
        cdef float* samples = <float*><char*>buf

        cdef PyBlockContext ctxt = PyBlockContext()
        for _ in range(100):
            check(be.begin_block(ctxt.get()))

            for i in range(self.host_system.block_size):
                samples[i] = float(i) / self.host_system.block_size
            check(be.output(ctxt.get(), b"left", <BufferPtr>samples))
            check(be.output(ctxt.get(), b"right", <BufferPtr>samples))

            check(be.end_block(ctxt.get()))

        be.cleanup()


class BackendTest(BackendTestMixin, unittest.TestCase):
    pass
