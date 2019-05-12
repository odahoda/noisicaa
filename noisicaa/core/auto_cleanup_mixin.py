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

from typing import Any, List, Callable


class AutoCleanupMixin(object):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)  # type: ignore

        self.__cleanup_functions = []  # type: List[Callable[[], None]]

    def add_cleanup_function(self, func: Callable[[], None]) -> None:
        self.__cleanup_functions.append(func)

    def cleanup(self) -> None:
        while self.__cleanup_functions:
            func = self.__cleanup_functions.pop(0)
            func()
