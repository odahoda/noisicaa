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

import logging
from typing import Any, Callable

from PySide2 import QtCore

from noisicaa import core
from noisicaa import value_types
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import slots

logger = logging.getLogger(__name__)


class ControlValueConnector(
        ui_base.ProjectMixin,
        slots.SlotContainer,
        core.AutoCleanupMixin,
        QtCore.QObject
):
    value, setValue, valueChanged = slots.slot(float, 'value')

    def __init__(
            self, *,
            node: music.BaseNode,
            name: str,
            **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__name = name

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)
        self.__generation = self.__node.control_value_map.generation(self.__name)

        self.setValue(self.__node.control_value_map.value(self.__name))

        self.valueChanged.connect(self.__onValueEdited)
        self.__listeners.add(self.__node.control_value_map.control_value_changed.add(
            self.__name, self.__onValueChanged))

    def __onValueEdited(self, value: float) -> None:
        if value != self.__node.control_value_map.value(self.__name):
            self.__generation += 1
            with self.project.apply_mutations(
                    '%s: Change control value "%s"' % (self.__node.name, self.__name)):
                self.__node.set_control_value(self.__name, value, self.__generation)

    def __onValueChanged(
            self, change: music.PropertyValueChange[value_types.ControlValue]) -> None:
        if change.new_value.generation < self.__generation:
            return

        self.__generation = change.new_value.generation
        self.setValue(change.new_value.value)

    def connect(self, getter: QtCore.SignalInstance, setter: Callable[[float], None]) -> None:
        getter.connect(self.setValue)
        setter(self.value())
        self.valueChanged.connect(setter)
