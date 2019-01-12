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
from typing import Iterator, Tuple


class PyURIDMapper(object):
    def map(self, uri: str) -> int: ...
    def unmap(self, urid: int) -> str: ...


class PyDynamicURIDMapper(PyURIDMapper):
    def known(self, uri: str) -> bool: ...
    def list(self) -> Iterator[Tuple[str, int]]: ...


class PyProxyURIDMapper(PyURIDMapper):
    def __init__(self, *, tmp_dir: str, server_address: str) -> None: ...
    async def setup(self, event_loop: asyncio.AbstractEventLoop) -> None: ...
    async def cleanup(self, event_loop: asyncio.AbstractEventLoop) -> None: ...
