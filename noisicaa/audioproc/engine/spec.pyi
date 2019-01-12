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

from typing import Any, Dict

from noisicaa import audioproc
from . import buffers
from . import control_value
from . import processor as processor_lib
from . import realm

opcode_map = ...  # type: Dict[str, int]
opname = ...  # type: Dict[int, str]


class PySpec(object):
    bpm = ...  # type: int
    duration = ...  # type: audioproc.MusicalTime

    def __init__(self) -> None: ...
    def dump(self) -> str: ...
    def append_buffer(self, name: str, buf_type: buffers.PyBufferType) -> None: ...
    def append_control_value(self, cv: control_value.PyControlValue) -> None: ...
    def append_processor(self, processor: processor_lib.PyProcessor) -> None: ...
    def append_child_realm(self, child_realm: realm.PyRealm) -> None: ...
    def append_opcode(self, opcode: str, *args: Any) -> None: ...
