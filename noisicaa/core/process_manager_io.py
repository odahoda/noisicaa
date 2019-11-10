#!/usr/bin/python3

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
import errno
import logging
import os

logger = logging.getLogger(__name__)


class ChildConnection(object):
    def __init__(self, fd_in: int, fd_out: int) -> None:
        self.fd_in = fd_in
        self.fd_out = fd_out

        self.__reader_state = 0
        self.__reader_buf = None  # type: bytearray
        self.__reader_length = None  # type: int

    def write(self, request: bytes) -> None:
        header = b'#%d\n' % len(request)
        msg = header + request
        while msg:
            written = os.write(self.fd_out, msg)
            msg = msg[written:]

    def __reader_start(self) -> None:
        self.__reader_state = 0
        self.__reader_buf = None
        self.__reader_length = None

    def __read_internal(self) -> None:
        if self.__reader_state == 0:
            d = os.read(self.fd_in, 1)
            if not d:
                raise OSError(errno.EBADF, "File descriptor closed")
            assert d == b'#', d
            self.__reader_buf = bytearray()
            self.__reader_state = 1

        elif self.__reader_state == 1:
            d = os.read(self.fd_in, 1)
            if not d:
                raise OSError(errno.EBADF, "File descriptor closed")
            elif d == b'\n':
                self.__reader_length = int(self.__reader_buf)
                self.__reader_buf = bytearray()
                self.__reader_state = 2
            else:
                self.__reader_buf += d

        elif self.__reader_state == 2:
            if len(self.__reader_buf) < self.__reader_length:
                d = os.read(self.fd_in, self.__reader_length - len(self.__reader_buf))
                if not d:
                    raise OSError(errno.EBADF, "File descriptor closed")
                self.__reader_buf += d

            if len(self.__reader_buf) == self.__reader_length:
                self.__reader_state = 3

    @property
    def __reader_done(self) -> bool:
        return self.__reader_state == 3

    @property
    def __reader_response(self) -> bytes:
        assert self.__reader_done
        return self.__reader_buf

    def read(self) -> bytes:
        self.__reader_start()
        while not self.__reader_done:
            self.__read_internal()
        return self.__reader_response

    async def read_async(self, event_loop: asyncio.AbstractEventLoop) -> bytes:
        done = asyncio.Event(loop=event_loop)
        def read_cb() -> None:
            try:
                self.__read_internal()

            except OSError:
                event_loop.remove_reader(self.fd_in)
                done.set()
                return

            except:
                event_loop.remove_reader(self.fd_in)
                raise

            if self.__reader_done:
                event_loop.remove_reader(self.fd_in)
                done.set()

        self.__reader_start()
        event_loop.add_reader(self.fd_in, read_cb)
        await done.wait()

        if self.__reader_done:
            return self.__reader_response
        else:
            raise OSError("Failed to read from connection")

    def close(self) -> None:
        os.close(self.fd_in)
        os.close(self.fd_out)
