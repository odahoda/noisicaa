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
from typing import cast, Any, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model_base
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import control_value_dial
from noisicaa.ui.graph import base_node
from . import model
from . import commands
from . import processor_messages

logger = logging.getLogger(__name__)


def fmt_value(value: float) -> str:
    prec = max(0, min(3 - int(math.log10(max(abs(value), 0.0001))), 3))
    return '%.*f' % (prec, value)


def clearLayout(layout: QtWidgets.QLayout) -> None:
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item.layout():
            clearLayout(item.layout())
        if item.widget():
            item.widget().setParent(None)


class LearnButton(QtWidgets.QToolButton):
    def __init__(self) -> None:
        super().__init__()

        self.setText("L")
        self.setCheckable(True)

        self.__default_bg = self.palette().color(QtGui.QPalette.Button)
        self.__timer = QtCore.QTimer()
        self.__timer.setInterval(250)
        self.__timer.timeout.connect(self.__blink)
        self.__blink_state = False

        self.toggled.connect(self.__toggledChanged)

    def __blink(self) -> None:
        self.__blink_state = not self.__blink_state
        palette = self.palette()
        if self.__blink_state:
            palette.setColor(self.backgroundRole(), QtGui.QColor(0, 255, 0))
        else:
            palette.setColor(self.backgroundRole(), self.__default_bg)
        self.setPalette(palette)

    def __toggledChanged(self, toggled: bool) -> None:
        if toggled:
            self.__timer.start()

        else:
            self.__timer.stop()
            palette = self.palette()
            palette.setColor(self.backgroundRole(), self.__default_bg)
            self.setPalette(palette)


class ChannelUI(ui_base.ProjectMixin, QtCore.QObject):
    def __init__(self, channel: model.MidiCCtoCVChannel, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__channel = channel
        self.__node = cast(model.MidiCCtoCV, channel.parent)

        self.__listeners = {}  # type: Dict[str, core.Listener]
        self.__learning = False

        self.__midi_channel = QtWidgets.QSpinBox()
        self.__midi_channel.setObjectName('channel[%016x]:midi_channel' % channel.id)
        self.__midi_channel.setRange(1, 16)
        self.__midi_channel.setValue(self.__channel.midi_channel + 1)
        self.__midi_channel.valueChanged.connect(self.__midiChannelEdited)
        self.__listeners['midi_channel'] = self.__channel.midi_channel_changed.add(
            self.__midiChannelChanged)

        self.__midi_controller = QtWidgets.QSpinBox()
        self.__midi_controller.setObjectName('channel[%016x]:midi_controller' % channel.id)
        self.__midi_controller.setRange(0, 127)
        self.__midi_controller.setValue(self.__channel.midi_controller)
        self.__midi_controller.valueChanged.connect(self.__midiControllerEdited)
        self.__listeners['midi_controller'] = self.__channel.midi_controller_changed.add(
            self.__midiControllerChanged)

        self.__learn_timeout = QtCore.QTimer()
        self.__learn_timeout.setInterval(5000)
        self.__learn_timeout.setSingleShot(True)
        self.__learn_timeout.timeout.connect(self.__learnStop)

        self.__learn = LearnButton()
        self.__learn.setObjectName('channel[%016x]:learn' % channel.id)
        self.__learn.toggled.connect(self.__learnClicked)

        self.__min_value = QtWidgets.QLineEdit()
        self.__min_value.setObjectName('channel[%016x]:min_value' % channel.id)
        min_value_validator = QtGui.QDoubleValidator()
        min_value_validator.setRange(-100000, 100000, 3)
        self.__min_value.setValidator(min_value_validator)
        self.__min_value.setText(fmt_value(self.__channel.min_value))
        self.__min_value.editingFinished.connect(self.__minValueEdited)
        self.__listeners['min_value'] = self.__channel.min_value_changed.add(self.__minValueChanged)

        self.__max_value = QtWidgets.QLineEdit()
        self.__max_value.setObjectName('channel[%016x]:max_value' % channel.id)
        max_value_validator = QtGui.QDoubleValidator()
        max_value_validator.setRange(-100000, 100000, 3)
        self.__max_value.setValidator(max_value_validator)
        self.__max_value.setText(fmt_value(self.__channel.max_value))
        self.__max_value.editingFinished.connect(self.__maxValueEdited)
        self.__listeners['max_value'] = self.__channel.max_value_changed.add(self.__maxValueChanged)

        self.__log_scale = QtWidgets.QCheckBox()
        self.__log_scale.setObjectName('channel[%016x]:log_scale' % channel.id)
        self.__log_scale.setChecked(self.__channel.log_scale)
        self.__log_scale.stateChanged.connect(self.__logScaleEdited)
        self.__listeners['log_scale'] = channel.log_scale_changed.add(self.__logScaleChanged)

        self.__current_value = control_value_dial.ControlValueDial()
        self.__current_value.setRange(0.0, 1.0)
        self.__current_value.setReadOnly(True)

    def addToLayout(self, layout: QtWidgets.QGridLayout, row: int) -> None:
        layout.addWidget(self.__learn, row, 0)
        layout.addWidget(self.__midi_channel, row, 1)
        layout.addWidget(self.__midi_controller, row, 2)
        layout.addWidget(self.__min_value, row, 3)
        layout.addWidget(self.__max_value, row, 4)
        layout.addWidget(self.__current_value, row, 5)

    def setCurrentValue(self, value: int) -> None:
        self.__current_value.setValue(value / 127.0)

    def cleanup(self) -> None:
        self.__learnStop()
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        learn_urid = 'http://noisicaa.odahoda.de/lv2/processor_cc_to_cv#learn'
        if learn_urid in msg and self.__learning:
            midi_channel, midi_controller = msg[learn_urid]
            self.__midi_channel.setValue(midi_channel + 1)
            self.__midi_controller.setValue(midi_controller)

            self.__learn_timeout.start()

    def __learnStart(self) -> None:
        if self.__learning:
            return
        self.__learning = True

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.call_async(self.project_view.sendNodeMessage(
            processor_messages.learn(self.__node, True)))

        self.__learn.setChecked(True)
        self.__learn_timeout.start()

    def __learnStop(self) -> None:
        if not self.__learning:
            return
        self.__learning = False

        self.__learn.setChecked(False)
        self.__learn_timeout.stop()

        self.call_async(self.project_view.sendNodeMessage(
            processor_messages.learn(self.__node, False)))

        self.__listeners.pop('node-messages').remove()

    def __learnClicked(self, checked: bool) -> None:
        if checked:
            self.__learnStart()
        else:
            self.__learnStop()

    def __midiChannelChanged(self, change: model_base.PropertyValueChange[int]) -> None:
        self.__midi_channel.setValue(change.new_value + 1)

    def __midiChannelEdited(self, value: int) -> None:
        value -= 1
        if value != self.__channel.midi_channel:
            self.send_command_async(commands.update_channel(
                self.__channel, set_midi_channel=value))

    def __midiControllerChanged(self, change: model_base.PropertyValueChange[int]) -> None:
        self.__midi_controller.setValue(change.new_value)

    def __midiControllerEdited(self, value: int) -> None:
        if value != self.__channel.midi_controller:
            self.send_command_async(commands.update_channel(
                self.__channel, set_midi_controller=value))

    def __minValueChanged(self, change: model_base.PropertyValueChange[float]) -> None:
        self.__min_value.setText(fmt_value(self.__channel.min_value))

    def __minValueEdited(self) -> None:
        state, _, _ = self.__min_value.validator().validate(self.__min_value.text(), 0)
        if state == QtGui.QValidator.Acceptable:
            value = float(self.__min_value.text())
            if value != self.__channel.min_value:
                self.send_command_async(commands.update_channel(
                    self.__channel, set_min_value=value))

    def __maxValueChanged(self, change: model_base.PropertyValueChange[float]) -> None:
        self.__max_value.setText(fmt_value(self.__channel.max_value))

    def __maxValueEdited(self) -> None:
        state, _, _ = self.__max_value.validator().validate(self.__max_value.text(), 0)
        if state == QtGui.QValidator.Acceptable:
            value = float(self.__max_value.text())
            if value != self.__channel.max_value:
                self.send_command_async(commands.update_channel(
                    self.__channel, set_max_value=value))

    def __logScaleChanged(self, change: model_base.PropertyValueChange[bool]) -> None:
        self.__log_scale.setChecked(self.__channel.log_scale)

    def __logScaleEdited(self, value: bool) -> None:
        if value != self.__channel.log_scale:
            self.send_command_async(commands.update_channel(
                self.__channel, set_log_scale=value))


class MidiCCtoCVNodeWidget(ui_base.ProjectMixin, QtWidgets.QScrollArea):
    def __init__(self, node: model.MidiCCtoCV, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.__channels = []  # type: List[ChannelUI]
        for idx, channel in enumerate(self.__node.channels):
            self.__addChannel(channel, idx)

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.__listeners['channels'] = self.__node.channels_changed.add(
            self.__channelsChanged)

        body = QtWidgets.QWidget(self)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(body)

        self.__num_channels = QtWidgets.QSpinBox()
        self.__num_channels.setSuffix(" channels")
        self.__num_channels.setKeyboardTracking(False)
        self.__num_channels.setRange(1, 100)
        self.__num_channels.setValue(len(self.__node.channels))
        self.__num_channels.valueChanged.connect(self.__numChannelsEdited)

        self.__channel_layout = QtWidgets.QGridLayout()
        self.__channel_layout.setColumnStretch(0, 0)  # learn
        self.__channel_layout.setColumnStretch(1, 1)  # MIDI channel
        self.__channel_layout.setColumnStretch(2, 1)  # MIDI controller
        self.__channel_layout.setColumnStretch(3, 1)  # min value
        self.__channel_layout.setColumnStretch(4, 1)  # max value
        self.__channel_layout.setColumnStretch(5, 0)  # current value
        self.__updateChannels()

        body_layout = QtWidgets.QVBoxLayout()
        l1 = QtWidgets.QHBoxLayout()
        l1.addWidget(self.__num_channels)
        l1.addStretch(1)
        body_layout.addLayout(l1)
        body_layout.addLayout(self.__channel_layout)
        body_layout.addStretch(1)
        body.setLayout(body_layout)

    def cleanup(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        for channel in self.__channels:
            channel.cleanup()
        self.__channels.clear()

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        cc_urid = 'http://noisicaa.odahoda.de/lv2/processor_cc_to_cv#cc'
        if cc_urid in msg:
            channel_idx, value = msg[cc_urid]
            if channel_idx < len(self.__channels):
                self.__channels[channel_idx].setCurrentValue(value)

    def __updateChannels(self) -> None:
        clearLayout(self.__channel_layout)

        row = 0
        self.__channel_layout.addWidget(QtWidgets.QLabel("MIDI Channel"), row, 1)
        self.__channel_layout.addWidget(QtWidgets.QLabel("Controller"), row, 2)
        self.__channel_layout.addWidget(QtWidgets.QLabel("Min"), row, 3)
        self.__channel_layout.addWidget(QtWidgets.QLabel("Max"), row, 4)
        row += 1

        for channel_ui in self.__channels:
            channel_ui.addToLayout(self.__channel_layout, row)
            row += 1

    def __channelsChanged(
            self,
            change: model_base.PropertyListChange[model.MidiCCtoCVChannel]
    ) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.__addChannel(change.new_value, change.index)

        elif isinstance(change, model_base.PropertyListDelete):
            self.__removeChannel(change.index)

        else:
            raise ValueError(type(change))

        self.__num_channels.setValue(len(self.__node.channels))
        self.__updateChannels()

    def __addChannel(self, channel: model.MidiCCtoCVChannel, index: int) -> None:
        channel_ui = ChannelUI(channel=channel, context=self.context)
        self.__channels.insert(index, channel_ui)

    def __removeChannel(self, index: int) -> None:
        channel_ui = self.__channels.pop(index)
        channel_ui.cleanup()

    def __numChannelsEdited(self, value: int) -> None:
        cmds = []

        for idx in range(len(self.__node.channels), value):
            cmds.append(commands.create_channel(
                self.__node, index=idx))

        for idx in range(value, len(self.__node.channels)):
            cmds.append(commands.delete_channel(
                self.__node.channels[idx]))

        if cmds:
            self.send_commands_async(*cmds)


class MidiCCtoCVNode(base_node.Node):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.MidiCCtoCV), type(node).__name__
        self.__widget = None  # type: MidiCCtoCVNodeWidget
        self.__node = node  # type: model.MidiCCtoCV

        super().__init__(node=node, **kwargs)

    def cleanup(self) -> None:
        if self.__widget is not None:
            self.__widget.cleanup()
        super().cleanup()

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = MidiCCtoCVNodeWidget(node=self.__node, context=self.context)
        return self.__widget
