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

from typing import Any

from noisicaa.lv2 import urid_mapper as urid_mapper_lib
from noisicaa.host_system import host_system as host_system_lib


class HostSystemMixin(object):
    urid_mapper = ...  # type: urid_mapper_lib.PyURIDMapper
    host_system = ...  # type: host_system_lib.PyHostSystem

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def setup_testcase(self) -> None: ...
    def cleanup_testcase(self) -> None: ...
