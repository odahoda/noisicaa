# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import asyncio
import concurrent.futures
import logging
import threading

from cpython.ref cimport PyObject
from cython.operator cimport dereference, preincrement

from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa.core.status cimport check
from . import urid_mapper_pb2

logger = logging.getLogger(__name__)


cdef class PyURIDMapper(object):
    cdef URIDMapper* get(self):
        raise NotImplementedError

    cdef URIDMapper* release(self):
        raise NotImplementedError

    def map(self, uri):
        cdef URIDMapper* mapper = self.get()

        b_uri = uri.encode('utf-8')
        cdef char* c_uri = b_uri
        cdef LV2_URID c_urid
        with nogil:
            c_urid = mapper.map(c_uri)
        return c_urid

    def unmap(self, urid):
        cdef URIDMapper* mapper = self.get()

        cdef LV2_URID c_urid = urid
        cdef const char *c_uri
        with nogil:
            c_uri = mapper.unmap(c_urid)
        if c_uri == NULL:
            return None
        return c_uri.decode('utf-8')


cdef class PyDynamicURIDMapper(PyURIDMapper):
    def __init__(self):
        super().__init__()

        self.__ptr.reset(new DynamicURIDMapper())
        self.__mapper = self.__ptr.get()

    cdef URIDMapper* get(self):
        return self.__mapper

    cdef URIDMapper* release(self):
        return self.__ptr.release()

    def known(self, uri):
        return self.__mapper.known(uri.encode('utf-8'))

    def list(self):
        cdef DynamicURIDMapper.const_iterator it = self.__mapper.begin()
        while it != self.__mapper.end():
            yield (dereference(it).first.decode('utf-8'), dereference(it).second)
            preincrement(it)


cdef class PyProxyURIDMapper(PyURIDMapper):
    def __init__(self, *, tmp_dir, server_address):
        super().__init__()

        self.__tmp_dir = tmp_dir
        self.__server_address = server_address

        self.__ptr.reset(new ProxyURIDMapper(self.map_cb, <PyObject*>self))
        self.__mapper = self.__ptr.get()

        self.__quit = None
        self.__client_thread = None
        self.__client_thread_ready = None
        self.__event_loop = None
        self.__cb_server = None
        self.__stub = None

    cdef URIDMapper* get(self):
        return self.__mapper

    cdef URIDMapper* release(self):
        return self.__ptr.release()

    async def setup(self, event_loop):
        self.__quit = concurrent.futures.Future()
        self.__client_thread_ready = concurrent.futures.Future()

        self.__client_thread = core.Thread(target=self.__client_main, event_loop=event_loop)
        self.__client_thread.start()

        ready_fut = asyncio.wrap_future(self.__client_thread_ready, loop=event_loop)
        await asyncio.wait([ready_fut], loop=event_loop)
        assert self.__client_thread_ready.done()
        self.__client_thread_ready.result()
        self.__client_thread_ready = None

    async def cleanup(self, event_loop):
        if self.__client_thread is not None:
            self.__quit.set_result(True)

            await self.__client_thread.join()
            self.__client_thread = None
            self.__quit = None

    @staticmethod
    cdef LV2_URID map_cb(void* handle, const char* uri) with gil:
        cdef PyProxyURIDMapper self = <object>handle
        cdef LV2_URID urid
        try:
            request = urid_mapper_pb2.MapRequest(uri=uri.decode('utf-8'))
            response = urid_mapper_pb2.MapResponse()
            fut = asyncio.run_coroutine_threadsafe(
                self.__stub.call('MAP', request, response),
                self.__event_loop)
            fut.result()
            return response.urid

        except Exception as exc:
            logger.exception("map_cb(%s) failed with an exception: %s", bytes(uri), exc)
            return 0

    def __handle_new_uris(self, request, response):
        for mapping in request.mappings:
            self.__mapper.insert(mapping.uri.encode('utf-8'), mapping.urid)

    def __client_main(self):
        logger.info("Starting URIDMapper client thread...")
        # Explicitly use the standard asyncio loop implementation. If the default loop
        # uses the gbulb implementation, then this will break.
        self.__event_loop = asyncio.SelectorEventLoop()
        try:
            logger.info("Starting event loop...")
            self.__event_loop.run_until_complete(self.__client_main_async())
        finally:
            logger.info("Closing event loop...")
            self.__event_loop.close()
            self.__event_loop = None
            logger.info("URIDMapper client thread finished.")

    async def __client_main_async(self):
        try:
            logger.info("Creating callback server...")
            self.__cb_server = ipc.Server(self.__event_loop, 'urid-mapper-cb', self.__tmp_dir)
            await self.__cb_server.setup()

            endpoint = ipc.ServerEndpoint('main')
            endpoint.add_handler(
                'NEW_URIS', self.__handle_new_uris,
                urid_mapper_pb2.NewURIsRequest, empty_message_pb2.EmptyMessage)
            await self.__cb_server.add_endpoint(endpoint)

            logger.info("Connecting to URIDMapper process...")
            self.__stub = ipc.Stub(self.__event_loop, self.__server_address)
            await self.__stub.connect(core.StartSessionRequest(
                callback_address=self.__cb_server.address))

            logger.info("URIDMapper client ready...")
            self.__client_thread_ready.set_result(True)

            quit_fut = asyncio.wrap_future(self.__quit, loop=self.__event_loop)
            await asyncio.wait([quit_fut], loop=self.__event_loop)
            assert self.__quit.done()
            self.__quit.result()

        finally:
            logger.info("Cleaning up URIDMapper client...")
            if self.__stub is not None:
                await self.__stub.close()
                self.__stub = None

            if self.__cb_server is not None:
                await self.__cb_server.cleanup()
                self.__cb_server = None

