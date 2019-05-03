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

import functools
import logging
import math
from typing import Any, Optional, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model_base
from noisicaa import music
from noisicaa import node_db
from noisicaa.ui import ui_base
from noisicaa.ui import control_value_connector
from noisicaa.ui import control_value_dial
from noisicaa.ui import slots
from noisicaa.ui.graph import base_node
from . import model_pb2
from . import model
from . import commands

logger = logging.getLogger(__name__)


def clearLayout(layout: QtWidgets.QLayout) -> None:
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item.layout():
            clearLayout(item.layout())
        if item.widget():
            item.widget().setParent(None)


class StepToggle(slots.SlotContainer, QtWidgets.QWidget):
    checked, setChecked, checkedChanged = slots.slot(bool, 'checked', default=False)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.checkedChanged.connect(lambda _: self.update())

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(50, 50)

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(32, 32)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return w

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        w = self.width()
        h = self.height()

        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHints(
                QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

            if self.isEnabled():
                border_color = QtGui.QColor(0, 0, 0)
                bg_color = QtGui.QColor(200, 200, 200)
                button_color = QtGui.QColor(100, 100, 255)

            else:
                border_color = QtGui.QColor(80, 80, 80)
                bg_color = QtGui.QColor(120, 120, 120)
                button_color = QtGui.QColor(80, 80, 80)

            pen = QtGui.QPen()
            pen.setColor(border_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QtGui.QBrush(bg_color))
            painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

            if self.checked():
                painter.fillRect(4, 4, w - 8, h - 8, button_color)

        finally:
            painter.end()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.setChecked(not self.checked())
            evt.accept()
            return

        super().mousePressEvent(evt)


def fmt_value(value: float) -> str:
    prec = max(0, min(3 - int(math.log10(max(abs(value), 0.0001))), 3))
    return '%.*f' % (prec, value)


def width_for(widget: QtWidgets.QWidget, text: str) -> int:
    f = widget.font()
    fm = QtGui.QFontMetrics(f)
    return fm.width(text)


class StepSequencerNodeWidget(ui_base.ProjectMixin, QtWidgets.QScrollArea):
    def __init__(self, node: model.StepSequencer, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__node.control_value_map.init()

        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        body = QtWidgets.QWidget(self)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(body)

        tempo_port = self.__node.description.ports[0]
        self.__tempo = control_value_dial.ControlValueDial()
        self.__tempo.setRange(tempo_port.float_value.min, tempo_port.float_value.max)
        self.__tempo.setDefault(tempo_port.float_value.default)
        if tempo_port.float_value.scale == node_db.FloatValueDescription.LOG:
            self.__tempo.setLogScale(True)
        self.__tempo_connector = control_value_connector.ControlValueConnector(
            node=self.__node, name='tempo', context=self.context)
        self.__tempo_connector.connect(self.__tempo.valueChanged, self.__tempo.setValue)

        self.__num_steps = QtWidgets.QSpinBox()
        self.__num_steps.setSuffix(" steps")
        self.__num_steps.setKeyboardTracking(False)
        self.__num_steps.setRange(2, 128)
        self.__num_steps.setValue(self.__node.num_steps)
        self.__num_steps.valueChanged.connect(self.__numStepsEdited)
        self.__listeners['num_steps'] = self.__node.num_steps_changed.add(
            self.__numStepsChanged)

        self.__num_channels = QtWidgets.QSpinBox()
        self.__num_channels.setSuffix(" channels")
        self.__num_channels.setKeyboardTracking(False)
        self.__num_channels.setRange(1, 100)
        self.__num_channels.setValue(len(self.__node.channels))
        self.__num_channels.valueChanged.connect(self.__numChannelsEdited)
        self.__listeners['num_channels'] = self.__node.channels_changed.add(
            self.__numChannelsChanged)

        self.__step_layout = QtWidgets.QGridLayout()
        self.__step_layout.setVerticalSpacing(5)
        self.__step_layout.setHorizontalSpacing(10)
        self.__step_layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        self.__current_step = None  # type: QtWidgets.QLabel
        self.__step_labels = []  # type: List[QtWidgets.QLabel]
        self.__matrix_listeners = []  # type: List[core.Listener]
        self.__updateStepMatrix()

        body_layout = QtWidgets.QVBoxLayout()
        l1 = QtWidgets.QHBoxLayout()
        l1.addWidget(self.__tempo)
        l1.addWidget(self.__num_steps)
        l1.addWidget(self.__num_channels)
        l1.addStretch(1)
        body_layout.addLayout(l1)
        body_layout.addLayout(self.__step_layout)
        body_layout.addStretch(1)
        body.setLayout(body_layout)

    def cleanup(self) -> None:
        if self.__tempo_connector is not None:
            self.__tempo_connector.cleanup()
            self.__tempo_connector = None

        for listener in self.__matrix_listeners:
            listener.remove()
        self.__matrix_listeners.clear()
        clearLayout(self.__step_layout)

        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

    def __updateStepMatrix(self) -> None:
        self.__step_labels.clear()
        self.__current_step = None

        for listener in self.__matrix_listeners:
            listener.remove()
        self.__matrix_listeners.clear()

        clearLayout(self.__step_layout)

        row = 0
        for col in range(self.__node.num_steps):
            step_label = QtWidgets.QLabel('%d' % (col + 1))
            step_label.setAlignment(Qt.AlignCenter)
            step_label.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.__step_layout.addWidget(step_label, row, col + 2)
            self.__step_labels.append(step_label)

        row += 1

        for channel in self.__node.channels:
            channel_layout = QtWidgets.QVBoxLayout()
            channel_layout.setContentsMargins(0, 0, 0, 0)
            channel_layout.setSpacing(0)
            channel_layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)

            channel_type = QtWidgets.QComboBox()
            for label, value in [("Value", model_pb2.StepSequencerChannel.VALUE),
                                 ("Trigger", model_pb2.StepSequencerChannel.TRIGGER),
                                 ("Gate", model_pb2.StepSequencerChannel.GATE)]:
                channel_type.addItem(label, value)
                if value == channel.type:
                    channel_type.setCurrentIndex(channel_type.count() - 1)
            channel_type.currentIndexChanged.connect(
                functools.partial(self.__channelTypeEdited, channel, channel_type))
            self.__matrix_listeners.append(channel.type_changed.add(
                functools.partial(self.__channelTypeChanged, channel, channel_type)))
            channel_layout.addWidget(channel_type)

            if channel.type in (model_pb2.StepSequencerChannel.GATE,
                                model_pb2.StepSequencerChannel.TRIGGER):
                pass

            else:
                assert channel.type == model_pb2.StepSequencerChannel.VALUE

                min_value = QtWidgets.QLineEdit()
                min_value_validator = QtGui.QDoubleValidator()
                min_value_validator.setRange(-100000, 100000, 3)
                min_value.setValidator(min_value_validator)
                min_value.setMinimumWidth(width_for(min_value, "100000") + 8)
                min_value.setText(fmt_value(channel.min_value))
                min_value.editingFinished.connect(
                    functools.partial(self.__channelMinValueEdited, channel, min_value))
                self.__matrix_listeners.append(channel.min_value_changed.add(
                    functools.partial(self.__channelMinValueChanged, channel, min_value)))

                max_value = QtWidgets.QLineEdit()
                max_value_validator = QtGui.QDoubleValidator()
                max_value_validator.setRange(-100000, 100000, 3)
                max_value.setValidator(max_value_validator)
                max_value.setMinimumWidth(width_for(max_value, "100000") + 8)
                max_value.setText(fmt_value(channel.max_value))
                max_value.editingFinished.connect(
                    functools.partial(self.__channelMaxValueEdited, channel, max_value))
                self.__matrix_listeners.append(channel.max_value_changed.add(
                    functools.partial(self.__channelMaxValueChanged, channel, max_value)))

                log_scale = QtWidgets.QCheckBox()
                log_scale.setChecked(channel.log_scale)
                log_scale.stateChanged.connect(
                    functools.partial(self.__channelLogScaleEdited, channel, log_scale))
                self.__matrix_listeners.append(channel.log_scale_changed.add(
                    functools.partial(self.__channelLogScaleChanged, channel, log_scale)))

                l1 = QtWidgets.QHBoxLayout()
                l1.setContentsMargins(0, 0, 0, 0)
                l1.setSpacing(0)
                l1.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
                l3 = QtWidgets.QVBoxLayout()
                l3.setContentsMargins(0, 0, 0, 0)
                l3.setSpacing(0)
                l3.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
                l3.addWidget(QtWidgets.QLabel("min"))
                l3.addWidget(min_value)
                l1.addLayout(l3)
                l4 = QtWidgets.QVBoxLayout()
                l4.setContentsMargins(0, 0, 0, 0)
                l4.setSpacing(0)
                l4.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
                l4.addWidget(QtWidgets.QLabel("max"))
                l4.addWidget(max_value)
                l1.addLayout(l4)
                channel_layout.addLayout(l1)
                l2 = QtWidgets.QHBoxLayout()
                l2.setContentsMargins(0, 0, 0, 0)
                l2.addStretch(1)
                l2.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
                l2.addWidget(log_scale)
                l2.addWidget(QtWidgets.QLabel("log"))
                l2.addStretch(1)
                channel_layout.addLayout(l2)

            channel_layout.addStretch(1)
            self.__step_layout.addLayout(channel_layout, row, 0, 2, 1)

            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.VLine)
            sep.setFrameShadow(QtWidgets.QFrame.Plain)
            self.__step_layout.addWidget(sep, row, 1, 2, 1)

            for col in range(self.__node.num_steps):
                step = channel.steps[col]

                if channel.type in (model_pb2.StepSequencerChannel.GATE,
                                    model_pb2.StepSequencerChannel.TRIGGER):
                    step_enabled = StepToggle()
                    step_enabled.setChecked(step.enabled)
                    step_enabled.checkedChanged.connect(
                        functools.partial(self.__stepEnabledEdited, step, step_enabled))
                    self.__matrix_listeners.append(step.enabled_changed.add(
                        functools.partial(self.__stepEnabledChanged, step, step_enabled)))
                    self.__step_layout.addWidget(step_enabled, row, col + 2)

                else:
                    assert channel.type == model_pb2.StepSequencerChannel.VALUE
                    step_value = control_value_dial.ControlValueDial()
                    step_value.setRange(0.0, 1.0)
                    step_value.setDefault(0.0)
                    step_value.setValue(step.value)
                    step_value.setDisplayFunc(functools.partial(self.__stepValueText, channel))
                    step_value.valueChanged.connect(
                        functools.partial(self.__stepValueEdited, step, step_value))
                    self.__matrix_listeners.append(step.value_changed.add(
                        functools.partial(self.__stepValueChanged, step, step_value)))
                    self.__step_layout.addWidget(step_value, row + 1, col + 2)
                    # mypy fails to infer the type of the lambdas.
                    self.__matrix_listeners.append(channel.min_value_changed.add(
                        lambda _, w=step_value: w.update()))  # type: ignore
                    self.__matrix_listeners.append(channel.max_value_changed.add(
                        lambda _, w=step_value: w.update()))  # type: ignore
                    self.__matrix_listeners.append(channel.log_scale_changed.add(
                        lambda _, w=step_value: w.update()))  # type: ignore

            row += 2

        self.__step_layout.setColumnStretch(0, 1)
        self.__step_layout.setColumnStretch(1, 1)
        for col in range(self.__node.num_steps):
            self.__step_layout.setColumnStretch(col + 2, 2)

    def __numStepsChanged(self, change: model_base.PropertyValueChange[int]) -> None:
        self.__num_steps.setValue(self.__node.num_steps)
        self.__updateStepMatrix()

    def __numStepsEdited(self, value: int) -> None:
        if value != self.__node.num_steps:
            self.send_command_async(commands.update(
                self.__node, set_num_steps=value))

    def __numChannelsChanged(
            self,
            change: model_base.PropertyListChange[model.StepSequencerChannel]
    ) -> None:
        self.__num_channels.setValue(len(self.__node.channels))
        self.__updateStepMatrix()

    def __numChannelsEdited(self, value: int) -> None:
        cmds = []

        for idx in range(len(self.__node.channels), value):
            cmds.append(commands.update(
                self.__node, add_channel=idx))

        for idx in range(value, len(self.__node.channels)):
            cmds.append(commands.delete_channel(
                self.__node.channels[idx]))

        if cmds:
            self.send_commands_async(*cmds)

    def __channelTypeChanged(
            self,
            channel: model.StepSequencerChannel,
            widget: QtWidgets.QComboBox,
            change: model_base.PropertyValueChange[int]
    ) -> None:
        self.__updateStepMatrix()

    def __channelTypeEdited(
            self,
            channel: model.StepSequencerChannel,
            widget: QtWidgets.QComboBox,
    ) -> None:
        value = widget.currentData()
        if value != channel.type:
            self.send_command_async(commands.update_channel(
                channel, set_type=value))

    def __channelMinValueChanged(
            self,
            channel: model.StepSequencerChannel,
            widget: control_value_dial.ControlValueDial,
            change: model_base.PropertyValueChange[float]
    ) -> None:
        widget.setText(fmt_value(channel.min_value))

    def __channelMinValueEdited(
            self,
            channel: model.StepSequencerChannel,
            widget: control_value_dial.ControlValueDial,
    ) -> None:
        state, _, _ = widget.validator().validate(widget.text(), 0)
        if state == QtGui.QValidator.Acceptable:
            value = float(widget.text())
            if value != channel.min_value:
                self.send_command_async(commands.update_channel(
                    channel, set_min_value=value))

    def __channelMaxValueChanged(
            self,
            channel: model.StepSequencerChannel,
            widget: control_value_dial.ControlValueDial,
            change: model_base.PropertyValueChange[float]
    ) -> None:
        widget.setText(fmt_value(channel.max_value))

    def __channelMaxValueEdited(
            self,
            channel: model.StepSequencerChannel,
            widget: control_value_dial.ControlValueDial,
    ) -> None:
        state, _, _ = widget.validator().validate(widget.text(), 0)
        if state == QtGui.QValidator.Acceptable:
            value = float(widget.text())
            if value != channel.max_value:
                self.send_command_async(commands.update_channel(
                    channel, set_max_value=value))

    def __channelLogScaleChanged(
            self,
            channel: model.StepSequencerChannel,
            widget: control_value_dial.ControlValueDial,
            change: model_base.PropertyValueChange[bool]
    ) -> None:
        widget.setChecked(channel.log_scale)

    def __channelLogScaleEdited(
            self,
            channel: model.StepSequencerChannel,
            widget: control_value_dial.ControlValueDial,
            value: bool
    ) -> None:
        if value != channel.log_scale:
            self.send_command_async(commands.update_channel(
                channel, set_log_scale=value))

    def __stepValueText(
            self,
            channel: model.StepSequencerChannel,
            value: float
    ) -> str:
        if channel.log_scale:
            try:
                value = (
                    math.exp(value * math.log(channel.max_value - channel.min_value + 1))
                    + channel.min_value - 1)
            except ValueError:
                value = channel.min_value
        else:
            value = value * (channel.max_value - channel.min_value) + channel.min_value
        return fmt_value(value)

    def __stepValueChanged(
            self,
            step: model.StepSequencerStep,
            widget: control_value_dial.ControlValueDial,
            change: model_base.PropertyValueChange[float]
    ) -> None:
        widget.setValue(step.value)

    def __stepValueEdited(
            self,
            step: model.StepSequencerStep,
            widget: control_value_dial.ControlValueDial,
            value: float
    ) -> None:
        if value != step.value:
            self.send_command_async(commands.update_step(
                step, set_value=value))

    def __stepEnabledChanged(
            self,
            step: model.StepSequencerStep,
            widget: StepToggle,
            change: model_base.PropertyValueChange[bool]
    ) -> None:
        widget.setChecked(step.enabled)

    def __stepEnabledEdited(
            self,
            step: model.StepSequencerStep,
            widget: StepToggle,
            value: bool
    ) -> None:
        if value != step.enabled:
            self.send_command_async(commands.update_step(
                step, set_enabled=value))

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        current_step_uri = 'http://noisicaa.odahoda.de/lv2/processor_step_sequencer#current_step'
        if current_step_uri in msg:
            current_step = msg[current_step_uri]
            if self.__current_step is not None:
                self.__current_step.setAutoFillBackground(False)
                self.__current_step.setBackgroundRole(QtGui.QPalette.NoRole)
                self.__current_step = None

            if current_step < len(self.__step_labels):
                self.__current_step = self.__step_labels[current_step]
                self.__current_step.setAutoFillBackground(True)
                self.__current_step.setBackgroundRole(QtGui.QPalette.Highlight)


class StepSequencerNode(base_node.Node):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.StepSequencer), type(node).__name__
        self.__widget = None  # type: StepSequencerNodeWidget
        self.__node = node  # type: model.StepSequencer

        super().__init__(node=node, **kwargs)

    def cleanup(self) -> None:
        if self.__widget is not None:
            self.__widget.cleanup()
        super().cleanup()

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = StepSequencerNodeWidget(node=self.__node, context=self.context)
        return self.__widget
