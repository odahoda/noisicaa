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

import logging
import os

from libc.string cimport strncpy
from cpython.ref cimport PyObject

from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from .plugin_ui_host cimport PluginUIHost, PyPluginUIHost

logger = logging.getLogger(__name__)


cdef extern from "errno.h" nogil:
    int errno

cdef extern from "pthread.h" nogil:
    ctypedef int pthread_condattr_t
    ctypedef int pthread_mutexattr_t

    cdef enum:
        PTHREAD_PROCESS_SHARED

    int pthread_mutexattr_init(pthread_mutexattr_t* attr)
    int pthread_mutexattr_setpshared(pthread_mutexattr_t* attr, int pshared)
    int pthread_mutex_init(pthread_mutex_t* mutex, const pthread_mutexattr_t* attr)
    int pthread_mutex_destroy(pthread_mutex_t* mutex)
    int pthread_mutex_lock(pthread_mutex_t* mutex)
    int pthread_mutex_unlock(pthread_mutex_t* mutex)
    int pthread_condattr_init(pthread_condattr_t* attr)
    int pthread_condattr_setpshared(pthread_condattr_t* attr, int pshared)
    int pthread_condattr_destroy(pthread_condattr_t* attr)
    int pthread_cond_init(pthread_cond_t* cond, const pthread_condattr_t* attr)
    int pthread_cond_destroy(pthread_cond_t* cond)
    int pthread_cond_signal(pthread_cond_t* cond)
    int pthread_cond_wait(pthread_cond_t* cond, pthread_mutex_t* mutex)

def build_memory_mapping(shmem_path, cond_offset, block_size, buffers):
    buf = bytearray(
        sizeof(PluginMemoryMapping) + len(buffers) * sizeof(PluginMemoryMapping.Buffer))
    cdef char* c_buf = buf
    cdef PluginMemoryMapping* memmap = <PluginMemoryMapping*>c_buf
    strncpy(memmap.shmem_path, os.fsencode(shmem_path), PATH_MAX)
    memmap.cond_offset = cond_offset
    memmap.block_size = block_size
    memmap.num_buffers = len(buffers)

    cdef PluginMemoryMapping.Buffer* bptr = <PluginMemoryMapping.Buffer*>(c_buf + sizeof(PluginMemoryMapping))
    for port_index, offset in buffers:
        bptr.port_index = port_index
        bptr.offset = offset
        bptr += 1

    return buf

cdef int pthread_check(int status) nogil except -1:
    if status != 0:
       with gil:
           raise OSError(errno, "pthread failure")
    return 0

def init_cond(char[:] buf not None, offset):
    cdef char* c_buf = &buf[0]
    cdef size_t c_offset = offset

    cdef PluginCond* pc = <PluginCond*>(c_buf + c_offset)
    c_offset += sizeof(PluginCond)

    pc.magic = 0x34638a33
    pc.set = False

    cdef pthread_mutexattr_t mutexattr
    pthread_check(pthread_mutexattr_init(&mutexattr))
    pthread_check(pthread_mutexattr_setpshared(&mutexattr, PTHREAD_PROCESS_SHARED))
    pthread_check(pthread_mutex_init(&pc.mutex, &mutexattr))

    cdef pthread_condattr_t condattr
    pthread_check(pthread_condattr_init(&condattr))
    pthread_check(pthread_condattr_setpshared(&condattr, PTHREAD_PROCESS_SHARED))
    pthread_check(pthread_cond_init(&pc.cond, &condattr))

    return c_offset


def cond_wait(char[:] buf not None, offset):
    cdef char* c_buf = &buf[0]
    cdef size_t c_offset = offset

    cdef PluginCond* pc = <PluginCond*>(c_buf + c_offset)

    with nogil:
        pthread_check(pthread_mutex_lock(&pc.mutex))
        try:
            while not pc.set:
                pthread_check(pthread_cond_wait(&pc.cond, &pc.mutex))

        finally:
            pthread_check(pthread_mutex_unlock(&pc.mutex))


def cond_clear(char[:] buf not None, offset):
    cdef char* c_buf = &buf[0]
    cdef size_t c_offset = offset

    cdef PluginCond* pc = <PluginCond*>(c_buf + c_offset)

    if pthread_mutex_lock(&pc.mutex) != 0:
        raise OSError(errno, "Failed to lock mutex")
    try:
        pc.set = False

    finally:
        if pthread_mutex_unlock(&pc.mutex) != 0:
            raise OSError(errno, "Failed to unlock mutex")


cdef class PyPluginHost(object):
    def __init__(self, spec, PyHostSystem host_system):
        cdef StatusOr[PluginHost*] stor_plugin_host = PluginHost.create(
            spec.SerializeToString(spec),
            host_system.get())
        check(stor_plugin_host)
        self.__plugin_host_ptr.reset(stor_plugin_host.result())
        self.__plugin_host = self.__plugin_host_ptr.get()

    cdef PluginHost* get(self) nogil:
        return self.__plugin_host

    cdef PluginHost* release(self) nogil:
        return self.__plugin_host_ptr.release()

    def setup(self):
        with nogil:
            check(self.__plugin_host.setup())

    def cleanup(self):
        # Only do cleanup, when we still own the processor.
        cdef PluginHost* plugin_host = self.__plugin_host_ptr.get()
        if plugin_host != NULL:
            with nogil:
                plugin_host.cleanup()

    def create_ui(self, control_value_change_cb):
        cdef PyPluginUIHost plugin_ui_host = PyPluginUIHost.__new__(PyPluginUIHost)
        plugin_ui_host.__control_value_change_cb = control_value_change_cb

        cdef StatusOr[PluginUIHost*] stor_plugin_ui_host = self.__plugin_host.create_ui(
            <PyObject*>plugin_ui_host, plugin_ui_host.__control_value_change)
        check(stor_plugin_ui_host)

        plugin_ui_host.init(stor_plugin_ui_host.result())
        return plugin_ui_host

    def main_loop(self, pipe_fd):
        cdef int c_pipe_fd = pipe_fd
        with nogil:
            check(self.__plugin_host.main_loop(c_pipe_fd))

    def exit_loop(self):
        with nogil:
            self.__plugin_host.exit_loop()

    def connect_port(self, port, char[:] data not None):
        cdef uint32_t c_port = port
        cdef BufferPtr c_data = <BufferPtr>&data[0]
        with nogil:
            check(self.__plugin_host.connect_port(c_port, c_data))

    def process_block(self, block_size):
        cdef uint32_t c_block_size = block_size
        with nogil:
            check(self.__plugin_host.process_block(c_block_size))
