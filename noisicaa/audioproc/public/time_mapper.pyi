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

from typing import Iterator
from .musical_time import PyMusicalTime, PyMusicalDuration
from noisicaa import music


class PyTimeMapper(object):
    bpm = ...  # type: int
    duration = ...  # type: PyMusicalDuration

    def __init__(self, sample_rate: int) -> None: ...
    def setup(self, project: music.BaseProject = None) -> None: ...
    def cleanup(self) -> None: ...
    @property
    def end_time(self) -> PyMusicalTime: ...
    @property
    def num_samples(self) -> int: ...
    def sample_to_musical_time(self, sample_time: int) -> PyMusicalTime: ...
    def musical_to_sample_time(self, musical_time: PyMusicalTime) -> int: ...
    def __iter__(self) -> Iterator[PyMusicalTime]: ...
    def find(self, t: PyMusicalTime) -> Iterator[PyMusicalTime]: ...

