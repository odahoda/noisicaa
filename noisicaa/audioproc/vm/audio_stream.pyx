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
from libcpp.string cimport string

import os

import capnp

from . import block_data_capnp


cdef class AudioStream(object):
    cdef unique_ptr[AudioStreamBase] stream

    def __init__(self):
        raise TypeError("Instances must be created with create_server/create_client.")

    @classmethod
    def create_server(self, address):
        if isinstance(address, str):
            address = os.fsencode(address)
        assert isinstance(address, bytes)
        cdef AudioStream obj = AudioStream.__new__(AudioStream)
        obj.stream.reset(new AudioStreamServer(address))
        return obj

    @classmethod
    def create_client(self, address):
        if isinstance(address, str):
            address = os.fsencode(address)
        assert isinstance(address, bytes)

        cdef AudioStream obj = AudioStream.__new__(AudioStream)
        obj.stream.reset(new AudioStreamClient(address))
        return obj

    @property
    def address(self):
        return os.fsdecode(self.stream.get().address())

    def setup(self):
        cdef AudioStreamBase* stream = self.stream.get()

        cdef Status status
        with nogil:
            status = stream.setup()
        check(status)

    def cleanup(self):
        cdef AudioStreamBase* stream = self.stream.get()
        with nogil:
            stream.cleanup()

    def close(self):
        cdef AudioStreamBase* stream = self.stream.get()
        with nogil:
            stream.close()

    def receive_bytes(self):
        cdef AudioStreamBase* stream = self.stream.get()

        cdef StatusOr[string] status_or_bytes
        with nogil:
            status_or_bytes = stream.receive_bytes();
        check(status_or_bytes)

        return bytes(status_or_bytes.result())

    def receive_block(self):
        return block_data_capnp.BlockData.from_bytes(self.receive_bytes())

    def send_bytes(self, const string& block_bytes):
        cdef AudioStreamBase* stream = self.stream.get()

        cdef Status status
        with nogil:
            status = stream.send_bytes(block_bytes);
        check(status)

    def send_block(self, block_data):
        return self.send_bytes(block_data.to_bytes())
