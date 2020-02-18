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

from typing import Iterator, Optional

from noisicaa import core
from noisicaa import audioproc
from . import buffer_arena
from . import message_queue


class PyBlockContext(object):
    sample_pos = ...  # type: int

    def __init__(self, buffer_arena: Optional[buffer_arena.PyBufferArena] = None) -> None: ...
    def clear_time_map(self, block_size: int) -> None: ...
    def set_sample_time(
            self, idx: int, start_time: audioproc.MusicalTime, end_time: audioproc.MusicalTime
    ) -> None: ...
    @property
    def perf(self) -> core.PerfStats: ...
    def create_out_messages(self) -> None: ...
    @property
    def out_messages(self) -> Iterator[message_queue.PyMessage]: ...
    def set_input_events(self, buf: bytes) -> None: ...
