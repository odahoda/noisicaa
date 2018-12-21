#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

import logging
import operator
from typing import cast, Any, Dict, Tuple, Type, Callable, TypeVar

from PyQt5 import QtCore

logger = logging.getLogger(__name__)


# This should really be a subclass of QtCore.QObject, but PyQt5 doesn't support
# multiple inheritance with QObjects.
class SlotContainer(object):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)  # type: ignore

        self._slots = {}  # type: Dict[str, Any]


_type = type

T = TypeVar('T')
def slot(
        type: Type[T],  # pylint: disable=redefined-builtin
        name: str,
        *,
        default: T = None,
        equality: Callable = None
) -> Tuple[Callable[[SlotContainer], T], Callable[[SlotContainer, T], None], QtCore.pyqtSignal]:
    assert isinstance(type, _type), type
    if equality is None:
        if type in (int, float, bool, str):
            equality = operator.eq
        else:
            equality = operator.is_

    signal = QtCore.pyqtSignal(type)

    def getter(self: SlotContainer) -> T:
        return self._slots.get(name, default)

    def setter(self: SlotContainer, value: T) -> None:
        if not isinstance(value, type):
            raise TypeError("Expected %s, got %s" % (type.__name__, _type(value).__name__))

        current_value = self._slots.get(name, default)
        if not equality(value, current_value):
            logger.debug("Slot %s on %s set to %s", name, self, value)
            self._slots[name] = value
            sig_inst = signal.__get__(cast(QtCore.QObject, self))
            sig_inst.emit(value)

    return getter, setter, signal
