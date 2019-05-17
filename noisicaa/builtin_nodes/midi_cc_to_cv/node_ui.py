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
from typing import cast, Any, Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import control_value_dial
from noisicaa.ui import property_connector
from noisicaa.ui.graph import base_node
from . import model
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


class MidiChannelSpinBox(QtWidgets.QSpinBox):
    def textFromValue(self, value: int) -> str:
        return super().textFromValue(value + 1)

    def valueFromText(self, text: str) -> int:
        return super().valueFromText(text) - 1

    def validate(self, text: str, pos: int) -> Tuple[QtGui.QValidator.State, str, int]:
        text = text.strip()
        if not text:
            return (QtGui.QValidator.Intermediate, text, pos)

        try:
            value = int(text) - 1
        except ValueError:
            return (QtGui.QValidator.Invalid, text, pos)

        if self.minimum() <= value <= self.maximum():
            return (QtGui.QValidator.Acceptable, text, pos)

        return (QtGui.QValidator.Invalid, text, pos)


class ChannelUI(ui_base.ProjectMixin, core.AutoCleanupMixin, QtCore.QObject):
    def __init__(self, channel: model.MidiCCtoCVChannel, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__channel = channel
        self.__node = cast(model.MidiCCtoCV, channel.parent)

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)
        self.__learning = False

        self.__midi_channel = MidiChannelSpinBox()
        self.__midi_channel.setObjectName('channel[%016x]:midi_channel' % channel.id)
        self.__midi_channel.setKeyboardTracking(False)
        self.__midi_channel.setRange(0, 15)
        self.__midi_channel_connector = property_connector.QSpinBoxConnector(
            self.__midi_channel, self.__channel, 'midi_channel',
            mutation_name='%s: Change MIDI channel' % self.__node.name,
            context=self.context)
        self.add_cleanup_function(self.__midi_channel_connector.cleanup)

        self.__midi_controller = QtWidgets.QSpinBox()
        self.__midi_controller.setObjectName('channel[%016x]:midi_controller' % channel.id)
        self.__midi_controller.setRange(0, 127)
        self.__midi_controller_connector = property_connector.QSpinBoxConnector(
            self.__midi_controller, self.__channel, 'midi_controller',
            mutation_name='%s: Change MIDI controller' % self.__node.name,
            context=self.context)
        self.add_cleanup_function(self.__midi_controller_connector.cleanup)

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
        self.__min_value_connector = property_connector.QLineEditConnector[float](
            self.__min_value, self.__channel, 'min_value',
            mutation_name='%s: Change min. value' % self.__node.name,
            parse_func=float,
            display_func=fmt_value,
            context=self.context)
        self.add_cleanup_function(self.__min_value_connector.cleanup)

        self.__max_value = QtWidgets.QLineEdit()
        self.__max_value.setObjectName('channel[%016x]:max_value' % channel.id)
        max_value_validator = QtGui.QDoubleValidator()
        max_value_validator.setRange(-100000, 100000, 3)
        self.__max_value.setValidator(max_value_validator)
        self.__max_value_connector = property_connector.QLineEditConnector[float](
            self.__max_value, self.__channel, 'max_value',
            mutation_name='%s: Change max. value' % self.__node.name,
            parse_func=float,
            display_func=fmt_value,
            context=self.context)
        self.add_cleanup_function(self.__max_value_connector.cleanup)

        self.__log_scale = QtWidgets.QCheckBox()
        self.__log_scale.setObjectName('channel[%016x]:log_scale' % channel.id)
        self.__log_scale_connector = property_connector.QCheckBoxConnector(
            self.__log_scale, self.__channel, 'log_scale',
            mutation_name='%s: Change log scale' % self.__node.name,
            context=self.context)
        self.add_cleanup_function(self.__log_scale_connector.cleanup)

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
        super().cleanup()

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

        del self.__listeners['node-messages']

    def __learnClicked(self, checked: bool) -> None:
        if checked:
            self.__learnStart()
        else:
            self.__learnStop()


class MidiCCtoCVNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QScrollArea):
    def __init__(self, node: model.MidiCCtoCV, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__listeners = core.ListenerMap[str]()

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
        for channel in self.__channels:
            channel.cleanup()
        self.__channels.clear()
        super().cleanup()

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
            change: music.PropertyListChange[model.MidiCCtoCVChannel]
    ) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addChannel(change.new_value, change.index)

        elif isinstance(change, music.PropertyListDelete):
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
        if value != len(self.__node.channels):
            with self.project.apply_mutations('%s: Change channel count' % self.__node.name):
                for idx in range(len(self.__node.channels), value):
                    self.__node.create_channel(idx)

                for idx in reversed(range(value, len(self.__node.channels))):
                    self.__node.delete_channel(self.__node.channels[idx])


class MidiCCtoCVNode(base_node.Node):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.MidiCCtoCV), type(node).__name__
        self.__widget = None  # type: MidiCCtoCVNodeWidget
        self.__node = node  # type: model.MidiCCtoCV

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = MidiCCtoCVNodeWidget(node=self.__node, context=self.context)
        self.__widget.add_cleanup_function(self.__widget.cleanup)
        return self.__widget
