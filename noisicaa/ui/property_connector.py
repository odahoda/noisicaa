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
from typing import Any, Callable, Generic, TypeVar

from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import device_list

logger = logging.getLogger(__name__)

W = TypeVar('W', bound=QtWidgets.QWidget)
V = TypeVar('V')


class PropertyConnector(Generic[V, W], ui_base.ProjectMixin, core.AutoCleanupMixin, object):
    def __init__(
            self,
            widget: W,
            obj: music.ObjectBase,
            prop: str,
            *,
            mutation_name: str,
            **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._widget = widget
        self._obj = obj
        self._prop_name = prop
        self._mutation_name = mutation_name

        self._connectToWidget()
        listener = self._obj.change_callbacks[self._prop_name].add(self._propertyChanged)
        self.add_cleanup_function(listener.remove)

    def value(self) -> V:
        return getattr(self._obj, self._prop_name)

    def setValue(self, value: V) -> None:
        if value != getattr(self._obj, self._prop_name):
            with self.project.apply_mutations(self._mutation_name):
                setattr(self._obj, self._prop_name, value)

    def _connectToWidget(self) -> None:
        raise NotImplementedError

    def _propertyChanged(self, change: music.PropertyValueChange) -> None:
        raise NotImplementedError


class PortSelectorConnector(PropertyConnector[str, device_list.PortSelector]):
    def _connectToWidget(self) -> None:
        self._widget.setSelectedPort(self.value())
        connection = self._widget.selectedPortChanged.connect(self.setValue)
        self.add_cleanup_function(lambda: self._widget.selectedPortChanged.disconnect(connection))

    def _propertyChanged(self, change: music.PropertyValueChange) -> None:
        self._widget.setSelectedPort(change.new_value)


class QComboBoxConnector(Generic[V], PropertyConnector[V, QtWidgets.QComboBox]):
    def _connectToWidget(self) -> None:
        idx = self._widget.findData(self.value())
        if idx >= 0:
            self._widget.setCurrentIndex(idx)
        connection = self._widget.currentIndexChanged.connect(self._widgetChanged)
        self.add_cleanup_function(lambda: self._widget.currentIndexChanged.disconnect(connection))

    def _widgetChanged(self) -> None:
        self.setValue(self._widget.currentData())

    def _propertyChanged(self, change: music.PropertyValueChange) -> None:
        idx = self._widget.findData(change.new_value)
        if idx >= 0:
            self._widget.setCurrentIndex(idx)


class QSpinBoxConnector(PropertyConnector[int, QtWidgets.QSpinBox]):
    def _connectToWidget(self) -> None:
        self._widget.setValue(self.value())
        connection = self._widget.valueChanged.connect(self.setValue)
        self.add_cleanup_function(lambda: self._widget.valueChanged.disconnect(connection))

    def _propertyChanged(self, change: music.PropertyValueChange) -> None:
        self._widget.setValue(change.new_value)


class QLineEditConnector(Generic[V], PropertyConnector[V, QtWidgets.QLineEdit]):
    def __init__(
            self,
            widget: QtWidgets.QLineEdit,
            obj: music.ObjectBase,
            prop: str,
            *,
            parse_func: Callable[[str], V],
            display_func: Callable[[V], str],
            **kwargs: Any) -> None:
        self.__parse_func = parse_func
        self.__display_func = display_func
        super().__init__(widget, obj, prop, **kwargs)

    def _connectToWidget(self) -> None:
        self._widget.setText(self.__display_func(self.value()))
        connection = self._widget.editingFinished.connect(self._widgetChanged)
        self.add_cleanup_function(lambda: self._widget.editingFinished.disconnect(connection))

    def _widgetChanged(self) -> None:
        text = self._widget.text()
        validator = self._widget.validator()
        if validator is not None:
            state, _, _ = validator.validate(self._widget.text(), 0)
            if state != QtGui.QValidator.Acceptable:
                return

        value = self.__parse_func(text)
        self.setValue(value)

    def _propertyChanged(self, change: music.PropertyValueChange) -> None:
        self._widget.setText(self.__display_func(change.new_value))


class QCheckBoxConnector(PropertyConnector[bool, QtWidgets.QCheckBox]):
    def _connectToWidget(self) -> None:
        self._widget.setChecked(self.value())
        connection = self._widget.stateChanged.connect(self.setValue)
        self.add_cleanup_function(lambda: self._widget.stateChanged.disconnect(connection))

    def _propertyChanged(self, change: music.PropertyValueChange) -> None:
        self._widget.setChecked(change.new_value)
