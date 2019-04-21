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
from noisicaa import model
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import control_value_dial
from noisicaa.ui.graph import base_node
from . import client_impl
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


controller_names = {
    0: "Bank Select",
    1: "Modulation Wheel or Lever",
    2: "Breath Controller",
    4: "Foot Controller",
    5: "Portamento Time",
    6: "Data Entry",
    7: "Channel Volume",
    8: "Balance",
    10:	"Pan",
    11:	"Expression Controller",
    12:	"Effect Control 1",
    13:	"Effect Control 2",
    16:	"General Purpose Controller 1",
    17:	"General Purpose Controller 2",
    18:	"General Purpose Controller 3",
    19:	"General Purpose Controller 4",
    32:	"Bank Select (LSB)",
    33:	"Modulation Wheel or Lever (LSB)",
    34:	"Breath Controller (LSB)",
    36:	"Foot Controller (LSB)",
    37:	"Portamento Time (LSB)",
    38:	"Data Entry (LSB)",
    39:	"Channel Volume (LSB)",
    40:	"Balance (LSB)",
    42:	"Pan (LSB)",
    43:	"Expression Controller (LSB)",
    44:	"Effect control 1 (LSB)",
    45:	"Effect control 2 (LSB)",
    48:	"General Purpose Controller 1 (LSB)",
    49:	"General Purpose Controller 2 (LSB)",
    50:	"General Purpose Controller 3 (LSB)",
    51:	"General Purpose Controller 4 (LSB)",
    64:	"Damper Pedal",
    65:	"Portamento",
    66:	"Sostenuto",
    67:	"Soft Pedal",
    68:	"Legato Footswitch",
    69:	"Hold 2",
    70:	"Sound Controller 1",
    71:	"Sound Controller 2",
    72:	"Sound Controller 3",
    73:	"Sound Controller 4",
    74:	"Sound Controller 5",
    75:	"Sound Controller 6",
    76:	"Sound Controller 7",
    77:	"Sound Controller 8",
    78:	"Sound Controller 9",
    79:	"Sound Controller 10",
    80:	"General Purpose Controller 5",
    81:	"General Purpose Controller 6",
    82:	"General Purpose Controller 7",
    83:	"General Purpose Controller 8",
    84:	"Portamento Control",
    88:	"High Resolution Velocity Prefix",
    91:	"Effects 1 Depth",
    92:	"Effects 2 Depth",
    93:	"Effects 3 Depth",
    94:	"Effects 4 Depth",
    95:	"Effects 5 Depth",
    96:	"Data Increment",
    97:	"Data Decrement)",
    98:	"Non-Registered Parameter Number (LSB)",
    99:	"Non-Registered Parameter Number (MSB)",
    100: "Registered Parameter Number (LSB)",
    101: "Registered Parameter Number (MSB)",
    120: "All Sound Off",
    121: "Reset All Controllers",
    122: "Local Control On/Off",
    123: "All Notes Off",
    124: "Omni Mode Off",
    125: "Omni Mode On",
    126: "Mono Mode On",
    127: "Poly Mode On",
}


class LearnButton(QtWidgets.QPushButton):
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
    def __init__(self, channel: client_impl.MidiCCtoCVChannel, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__channel = channel
        self.__node = cast(client_impl.MidiCCtoCV, channel.parent)

        self.__listeners = {}  # type: Dict[str, core.Listener]
        self.__learning = False

        self.__midi_channel = QtWidgets.QComboBox()
        self.__midi_channel.setObjectName('channel[%016x]:midi_channel' % channel.id)
        for ch in range(16):
            self.__midi_channel.addItem('%d' % (ch + 1), ch)
            if ch == self.__channel.midi_channel:
                self.__midi_channel.setCurrentIndex(self.__midi_channel.count() - 1)
        self.__midi_channel.currentIndexChanged.connect(self.__midiChannelEdited)
        self.__listeners['midi_channel'] = self.__channel.midi_channel_changed.add(
            self.__midiChannelChanged)

        self.__midi_controller = QtWidgets.QComboBox()
        self.__midi_controller.setObjectName('channel[%016x]:midi_controller' % channel.id)
        for ch in range(127):
            if ch in controller_names:
                name = '%d: %s' % (ch, controller_names[ch])
            else:
                name = '%d' % ch
            self.__midi_controller.addItem(name, ch)
            if ch == self.__channel.midi_controller:
                self.__midi_controller.setCurrentIndex(self.__midi_controller.count() - 1)
        self.__midi_controller.currentIndexChanged.connect(self.__midiControllerEdited)
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
        layout.addWidget(self.__midi_channel, row, 0)
        layout.addWidget(self.__midi_controller, row, 1)
        layout.addWidget(self.__learn, row, 2)
        layout.addWidget(self.__min_value, row, 3)
        layout.addWidget(self.__max_value, row, 4)
        layout.addWidget(self.__log_scale, row, 5)
        layout.addWidget(self.__current_value, row, 6)

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
            idx = self.__midi_channel.findData(midi_channel)
            if idx >= 0:
                self.__midi_channel.setCurrentIndex(idx)
            else:
                logger.error("MIDI channel %r not found.", midi_channel)
            idx = self.__midi_controller.findData(midi_controller)
            if idx >= 0:
                self.__midi_controller.setCurrentIndex(idx)
            else:
                logger.error("MIDI controller %r not found.", midi_controller)

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

    def __midiChannelChanged(self, change: model.PropertyValueChange[int]) -> None:
        idx = self.__midi_channel.findData(change.new_value)
        if idx >= 0:
            self.__midi_channel.setCurrentIndex(idx)
        else:
            logger.error("MIDI channel %r not found.", change.new_value)

    def __midiChannelEdited(self) -> None:
        value = self.__midi_channel.currentData()
        if value != self.__channel.midi_channel:
            self.send_command_async(commands.update_channel(
                self.__channel, set_midi_channel=value))

    def __midiControllerChanged(self, change: model.PropertyValueChange[int]) -> None:
        idx = self.__midi_controller.findData(change.new_value)
        if idx >= 0:
            self.__midi_controller.setCurrentIndex(idx)
        else:
            logger.error("MIDI controller %r not found.", change.new_value)

    def __midiControllerEdited(self) -> None:
        value = self.__midi_controller.currentData()
        if value != self.__channel.midi_controller:
            self.send_command_async(commands.update_channel(
                self.__channel, set_midi_controller=value))

    def __minValueChanged(self, change: model.PropertyValueChange[float]) -> None:
        self.__min_value.setText(fmt_value(self.__channel.min_value))

    def __minValueEdited(self) -> None:
        state, _, _ = self.__min_value.validator().validate(self.__min_value.text(), 0)
        if state == QtGui.QValidator.Acceptable:
            value = float(self.__min_value.text())
            if value != self.__channel.min_value:
                self.send_command_async(commands.update_channel(
                    self.__channel, set_min_value=value))

    def __maxValueChanged(self, change: model.PropertyValueChange[float]) -> None:
        self.__max_value.setText(fmt_value(self.__channel.max_value))

    def __maxValueEdited(self) -> None:
        state, _, _ = self.__max_value.validator().validate(self.__max_value.text(), 0)
        if state == QtGui.QValidator.Acceptable:
            value = float(self.__max_value.text())
            if value != self.__channel.max_value:
                self.send_command_async(commands.update_channel(
                    self.__channel, set_max_value=value))

    def __logScaleChanged(self, change: model.PropertyValueChange[bool]) -> None:
        self.__log_scale.setChecked(self.__channel.log_scale)

    def __logScaleEdited(self, value: bool) -> None:
        if value != self.__channel.log_scale:
            self.send_command_async(commands.update_channel(
                self.__channel, set_log_scale=value))


class MidiCCtoCVNodeWidget(ui_base.ProjectMixin, QtWidgets.QScrollArea):
    def __init__(self, node: client_impl.MidiCCtoCV, **kwargs: Any) -> None:
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
        for channel_ui in self.__channels:
            channel_ui.addToLayout(self.__channel_layout, row)
            row += 1

    def __channelsChanged(
            self,
            change: model.PropertyListChange[client_impl.MidiCCtoCVChannel]
    ) -> None:
        if isinstance(change, model.PropertyListInsert):
            self.__addChannel(change.new_value, change.index)

        elif isinstance(change, model.PropertyListDelete):
            self.__removeChannel(change.index)

        else:
            raise ValueError(type(change))

        self.__num_channels.setValue(len(self.__node.channels))
        self.__updateChannels()

    def __addChannel(self, channel: client_impl.MidiCCtoCVChannel, index: int) -> None:
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
        assert isinstance(node, client_impl.MidiCCtoCV), type(node).__name__
        self.__widget = None  # type: MidiCCtoCVNodeWidget
        self.__node = node  # type: client_impl.MidiCCtoCV

        super().__init__(node=node, **kwargs)

    def cleanup(self) -> None:
        if self.__widget is not None:
            self.__widget.cleanup()
        super().cleanup()

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = MidiCCtoCVNodeWidget(node=self.__node, context=self.context)
        return self.__widget
