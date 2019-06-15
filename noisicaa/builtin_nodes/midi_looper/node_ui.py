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
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui.graph import base_node
from noisicaa.builtin_nodes import processor_message_registry_pb2
from . import model

logger = logging.getLogger(__name__)


class MidiLooperNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QScrollArea):
    def __init__(self, node: model.MidiLooper, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        body = QtWidgets.QWidget(self)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(body)

        self.__duration = QtWidgets.QSpinBox()
        self.__duration.setObjectName('duration')
        self.__duration.setSuffix(" beats")
        self.__duration.setKeyboardTracking(False)
        self.__duration.setRange(1, 100)
        num_beats = self.__node.duration / audioproc.MusicalDuration(1, 4)
        assert num_beats.denominator == 1
        self.__duration.setValue(num_beats.numerator)
        self.__duration.valueChanged.connect(self.__durationEdited)
        self.__listeners['duration'] = self.__node.duration_changed.add(self.__durationChanged)

        self.__record = QtWidgets.QPushButton()
        self.__record.setText("Record")
        self.__record.clicked.connect(self.__recordClicked)

        self.__current_position = QtWidgets.QLineEdit()
        self.__current_position.setObjectName('current_position')
        self.__current_position.setReadOnly(True)

        l2 = QtWidgets.QHBoxLayout()
        l2.addWidget(self.__duration)
        l2.addStretch(1)

        l1 = QtWidgets.QVBoxLayout()
        l1.addLayout(l2)
        l1.addWidget(self.__record)
        l1.addWidget(self.__current_position)
        l1.addStretch(1)
        body.setLayout(l1)

    def __durationChanged(self, change: music.PropertyValueChange[audioproc.MusicalDuration]) -> None:
        num_beats = change.new_value / audioproc.MusicalDuration(1, 4)
        assert num_beats.denominator == 1
        self.__duration.setValue(num_beats.numerator)

    def __durationEdited(self, beats: int) -> None:
        duration = audioproc.MusicalDuration(beats, 4)
        if duration == self.__node.duration:
            return

        with self.project.apply_mutations('%s: Change duration' % self.__node.name):
            self.__node.set_duration(duration)

    def __recordClicked(self) -> None:
        msg = audioproc.ProcessorMessage(node_id=self.__node.pipeline_node_id)
        pb = msg.Extensions[processor_message_registry_pb2.midi_looper_record]
        pb.start = 1
        self.call_async(self.project_view.sendNodeMessage(msg))

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        current_position_urid = 'http://noisicaa.odahoda.de/lv2/processor_midi_looper#current_position'
        if current_position_urid in msg:
            numerator, denominator = msg[current_position_urid]
            current_position = audioproc.MusicalTime(numerator, denominator)
            self.__current_position.setText('%d%%' % int(100 * (current_position / self.__node.duration).to_float()))


class MidiLooperNode(base_node.Node):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.MidiLooper), type(node).__name__
        self.__widget = None  # type: MidiLooperNodeWidget
        self.__node = node  # type: model.MidiLooper

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = MidiLooperNodeWidget(node=self.__node, context=self.context)
        self.add_cleanup_function(self.__widget.cleanup)
        return self.__widget
