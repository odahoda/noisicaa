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
import math
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import property_connector

logger = logging.getLogger(__name__)


class TransferFunctionDisplay(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(
            self, *,
            transfer_function: music.TransferFunction,
            mutation_name_prefix: str,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__transfer_function = transfer_function
        self.__mutation_name_prefix = mutation_name_prefix

        self.setMinimumSize(60, 60)
        self.setMouseTracking(True)

        self.__bg_color = QtGui.QColor(0, 0, 0)
        self.__border_color = QtGui.QColor(100, 200, 100)
        self.__grid_color = QtGui.QColor(40, 60, 40)
        self.__center_color = QtGui.QColor(60, 100, 60)
        self.__plot_pen = QtGui.QPen(QtGui.QColor(255, 255, 255))
        self.__plot_pen.setWidth(2)
        self.__handle_pen = QtGui.QPen(QtGui.QColor(255, 255, 255))
        self.__handle_pen.setWidth(1)
        self.__handle_brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        self.__active_handle_brush = QtGui.QBrush(QtGui.QColor(100, 100, 255))

        self.__handles = {}  # type: Dict[str, QtCore.QRect]
        self.__active_handle = None  # type: str
        self.__drag_handle = None  # type: str
        self.__drag_handle_offset = None  # type: QtCore.QPoint

        self.__spec = self.__transfer_function.get_function_spec()

        listener = self.__transfer_function.object_changed.add(
            lambda _: self.__transferFunctionChanged())
        self.add_cleanup_function(listener.remove)

    def __transferFunctionChanged(self) -> None:
        self.__spec = self.__transfer_function.get_function_spec()
        self.update()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(100, 100)

    def hideEvent(self, evt: QtGui.QHideEvent) -> None:
        self.__handles.clear()
        super().hideEvent(evt)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        self.__handles.clear()
        super().resizeEvent(evt)

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(evt.rect(), self.__bg_color)

            w = self.width() - 10
            h = self.height() - 10

            for g in (1, 2, 3, 4, 6, 7, 8, 9, 5, 0, 10):
                if g in (0, 10):
                    color = self.__border_color
                elif g == 5:
                    color = self.__center_color
                else:
                    color = self.__grid_color

                painter.fillRect(int(g * (w - 1) / 10) + 5, 5, 1, h, color)
                painter.fillRect(5, int(g * (h - 1) / 10) + 5, w, 1, color)

            path = QtGui.QPainterPath()
            tfa = audioproc.TransferFunction(self.__spec)
            x_to_value = lambda value: (
                (self.__spec.input_max - self.__spec.input_min)
                * (value / (w - 1))
                + self.__spec.input_min)
            value_to_y = lambda value: int(
                (h - 1)
                * (value - self.__spec.output_min)
                / (self.__spec.output_max - self.__spec.output_min))

            for x in range(w):
                value = x_to_value(x)
                value = tfa(value)
                y = value_to_y(value)
                if x == 0:
                    path.moveTo(x + 5, h - y + 4)
                else:
                    path.lineTo(x + 5, h - y + 4)

            painter.setPen(self.__plot_pen)
            painter.drawPath(path)

            self.__handles.clear()
            handles_to_render = []
            if self.__spec.WhichOneof('type') in ('fixed', 'linear'):
                y1 = value_to_y(tfa(self.__spec.input_min))
                r = QtCore.QRect(3, h - y1 + 2, 6, 6)
                self.__handles['left'] = r
                handles_to_render.append('left')

                y2 = value_to_y(tfa(self.__spec.input_max))
                r = QtCore.QRect(w + 2, h - y2 + 2, 6, 6)
                self.__handles['right'] = r
                handles_to_render.append('right')

            elif self.__spec.WhichOneof('type') == 'gamma':
                x = int(0.3 * math.log10(self.__spec.gamma.value) * w) + w // 2
                y = value_to_y(tfa(x_to_value(x)))
                r = QtCore.QRect(x + 3, h - y + 2, 6, 6)
                self.__handles['center'] = r
                handles_to_render.append('center')

            for name in handles_to_render:
                rect = self.__handles[name]
                painter.setPen(self.__handle_pen)
                if name == self.__active_handle:
                    painter.setBrush(self.__active_handle_brush)
                else:
                    painter.setBrush(self.__handle_brush)
                painter.drawRect(QtCore.QRectF(rect).translated(-0.5, -0.5))

        finally:
            painter.end()

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__drag_handle is not None:
            if self.__spec.WhichOneof('type') in ('fixed', 'linear'):
                value = (
                    (self.height()
                     - max(5, min(self.height() - 6, evt.pos().y() - self.__drag_handle_offset.y()))
                     - 6)
                    / (self.height() - 11))
                value = (
                    (self.__spec.output_max - self.__spec.output_min)
                    * value
                    + self.__spec.output_min)
                if self.__spec.WhichOneof('type') == 'fixed':
                    if value != self.__transfer_function.fixed_value:
                        with self.project.apply_mutations(
                                '%s: Change fixed value' % self.__mutation_name_prefix):
                            self.__transfer_function.fixed_value = value

                else:
                    if (self.__drag_handle == 'left'
                            and value != self.__transfer_function.linear_left_value):
                        with self.project.apply_mutations(
                                '%s: Change linear mapping' % self.__mutation_name_prefix):
                            self.__transfer_function.linear_left_value = value

                    elif (self.__drag_handle == 'right'
                          and value != self.__transfer_function.linear_right_value):
                        with self.project.apply_mutations(
                                '%s: Change linear mapping' % self.__mutation_name_prefix):
                            self.__transfer_function.linear_right_value = value

            elif self.__spec.WhichOneof('type') == 'gamma':
                x = evt.pos().x() - self.__drag_handle_offset.x()
                value = max(
                    0.05,
                    min(20.0,
                        pow(10, (x - 5 - (self.width() - 10) // 2) / (0.3 * (self.width() - 10)))))
                if value != self.__transfer_function.gamma_value:
                    with self.project.apply_mutations(
                            '%s: Change gamma value' % self.__mutation_name_prefix):
                        self.__transfer_function.gamma_value = value

            else:
                raise AssertionError(self.__spec.WhichOneof('type'))

            self.update()
            return

        closest_handle = None
        closest_dist = None
        for name, rect in self.__handles.items():
            delta = rect.center() - evt.pos()
            dist = math.sqrt(delta.x() ** 2 + delta.y() ** 2)
            if dist < 20 and (closest_handle is None or dist < closest_dist):
                closest_handle = name
                closest_dist = dist

        if closest_handle != self.__active_handle:
            self.__active_handle = closest_handle
            self.update()

        super().mouseMoveEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__active_handle is not None:
            handle = self.__handles[self.__active_handle]
            self.__drag_handle = self.__active_handle
            self.__drag_handle_offset = evt.pos() - handle.center()
            self.update()
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__drag_handle is not None:
            self.__drag_handle = None
            self.__drag_handle_offset = None
            self.update()
            evt.accept()
            return

        super().mouseReleaseEvent(evt)


class TransferFunctionEditor(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(
            self, *,
            transfer_function: music.TransferFunction,
            mutation_name_prefix: str,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__transfer_function = transfer_function
        self.__mutation_name_prefix = mutation_name_prefix

        self.__stack = QtWidgets.QStackedWidget()
        type_to_stack_index = {}  # type: Dict[int, int]

        self.__fixed_value = QtWidgets.QDoubleSpinBox()
        self.__fixed_value.setKeyboardTracking(False)
        self.__fixed_value.setRange(0, 127)
        self.__fixed_value_connector = property_connector.QDoubleSpinBoxConnector(
            self.__fixed_value, self.__transfer_function, 'fixed_value',
            mutation_name='%s: Change fixed value' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__fixed_value_connector.cleanup)

        self.__fixed_params = QtWidgets.QWidget()
        l2 = QtWidgets.QVBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__fixed_value)
        self.__fixed_params.setLayout(l2)

        type_to_stack_index[music.TransferFunction.FIXED] = self.__stack.addWidget(
            self.__fixed_params)

        self.__linear_left_value = QtWidgets.QDoubleSpinBox()
        self.__linear_left_value.setKeyboardTracking(False)
        self.__linear_left_value.setRange(0, 127)
        self.__linear_left_value_connector = property_connector.QDoubleSpinBoxConnector(
            self.__linear_left_value, self.__transfer_function, 'linear_left_value',
            mutation_name='%s: Change linear mapping' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__linear_left_value_connector.cleanup)

        self.__linear_right_value = QtWidgets.QDoubleSpinBox()
        self.__linear_right_value.setKeyboardTracking(False)
        self.__linear_right_value.setRange(0, 127)
        self.__linear_right_value_connector = property_connector.QDoubleSpinBoxConnector(
            self.__linear_right_value, self.__transfer_function, 'linear_right_value',
            mutation_name='%s: Change linear mapping' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__linear_right_value_connector.cleanup)

        self.__linear_params = QtWidgets.QWidget()
        l3 = QtWidgets.QHBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__linear_left_value)
        l3.addWidget(self.__linear_right_value)
        self.__linear_params.setLayout(l3)

        type_to_stack_index[music.TransferFunction.LINEAR] = self.__stack.addWidget(
            self.__linear_params)

        self.__gamma_value = QtWidgets.QDoubleSpinBox()
        self.__gamma_value.setKeyboardTracking(False)
        self.__gamma_value.setRange(0.05, 20.0)
        self.__gamma_value.setSingleStep(0.1)
        self.__gamma_value_connector = property_connector.QDoubleSpinBoxConnector(
            self.__gamma_value, self.__transfer_function, 'gamma_value',
            mutation_name='%s: Change gamma value' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__gamma_value_connector.cleanup)

        self.__gamma_params = QtWidgets.QWidget()
        l2 = QtWidgets.QVBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__gamma_value)
        self.__gamma_params.setLayout(l2)

        type_to_stack_index[music.TransferFunction.GAMMA] = self.__stack.addWidget(
            self.__gamma_params)

        self.__type = QtWidgets.QComboBox()
        self.__type.addItem("Fixed", music.TransferFunction.FIXED)
        self.__type.addItem("Linear", music.TransferFunction.LINEAR)
        self.__type.addItem("Gamma", music.TransferFunction.GAMMA)
        self.__type.currentIndexChanged.connect(
            lambda _: self.__stack.setCurrentIndex(type_to_stack_index[self.__type.currentData()]))
        self.__type_connector = property_connector.QComboBoxConnector[int](
            self.__type, self.__transfer_function, 'type',
            mutation_name='%s: Change function type' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__type_connector.cleanup)

        self.__display = TransferFunctionDisplay(
            transfer_function=self.__transfer_function,
            mutation_name_prefix=self.__mutation_name_prefix,
            context=self.context)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__type)
        l1.addWidget(self.__stack)
        l1.addWidget(self.__display, 1)
        self.setLayout(l1)
