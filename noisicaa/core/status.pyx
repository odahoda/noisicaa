# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import os.path

class Error(Exception):
    pass


class ConnectionClosed(Exception):
    pass


cdef int check(const Status& status) nogil except -1:
    if status.is_connection_closed():
        with gil:
            raise ConnectionClosed('[%s:%d] Connection closed' % (
                os.path.relpath(
                    os.path.abspath(bytes(status.file()).decode('utf-8')),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))),
                status.line()))

    if status.is_error():
        with gil:
            raise Error('[%s:%d] %s' % (
                os.path.relpath(
                    os.path.abspath(bytes(status.file()).decode('utf-8')),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))),
                status.line(),
                bytes(status.message()).decode('utf-8')))
    return 0

