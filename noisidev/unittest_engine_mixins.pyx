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


cdef class HostSystemMixin(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.urid_mapper = None
        self.host_system = None

    def setup_testcase(self):
        self.urid_mapper = urid_mapper.PyDynamicURIDMapper()
        self.host_system = host_system.PyHostSystem(self.urid_mapper)
        self.host_system.setup()

    def cleanup_testcase(self):
        if self.host_system is not None:
            self.host_system.cleanup()

        self.host_system = None
        self.urid_mapper = None
