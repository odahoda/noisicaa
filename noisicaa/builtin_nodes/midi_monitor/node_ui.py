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
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa import value_types
from noisicaa.ui import ui_base
from noisicaa.ui import slots
from noisicaa.ui.graph import base_node
from . import model

logger = logging.getLogger(__name__)


class MidiMonitorNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, node: model.MidiMonitor, session_prefix: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__slot_connections = slots.SlotConnectionManager(
            session_prefix='midi_monitor:%016x:%s' % (self.__node.id, session_prefix),
            context=self.context)
        self.add_cleanup_function(self.__slot_connections.cleanup)

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.__paused = False

        self.__pause_action = QtWidgets.QAction("Pause", self)
        self.__pause_action.setIcon(QtGui.QIcon.fromTheme('media-playback-pause'))
        self.__pause_action.setCheckable(True)
        self.__pause_action.toggled.connect(self.__pauseToggled)
        self.__slot_connections.connect(
            'paused',
            self.__pause_action.setChecked,
            self.__pause_action.toggled,
            False)

        self.__clear_action = QtWidgets.QAction("Clear", self)
        self.__clear_action.setIcon(QtGui.QIcon.fromTheme('edit-delete'))
        self.__clear_action.triggered.connect(self.__clearClicked)

        self.__pause = QtWidgets.QToolButton()
        self.__pause.setDefaultAction(self.__pause_action)
        self.__pause.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.__clear = QtWidgets.QToolButton()
        self.__clear.setDefaultAction(self.__clear_action)
        self.__clear.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.__events = QtWidgets.QTableWidget()
        self.__events.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.__events.setColumnCount(5)
        self.__events.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem("Time"))
        self.__events.setHorizontalHeaderItem(1, QtWidgets.QTableWidgetItem("Type"))
        self.__events.setHorizontalHeaderItem(2, QtWidgets.QTableWidgetItem("Channel"))
        self.__events.setHorizontalHeaderItem(3, QtWidgets.QTableWidgetItem("Data 1"))
        self.__events.setHorizontalHeaderItem(4, QtWidgets.QTableWidgetItem("Data 2"))
        self.__events.horizontalHeader().setStretchLastSection(True)
        self.__events.horizontalHeader().setSectionsClickable(False)
        self.__events.verticalHeader().setVisible(False)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__pause)
        l2.addWidget(self.__clear)
        l2.addStretch(1)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addLayout(l2)
        l1.addWidget(self.__events)
        self.setLayout(l1)

    def __pauseToggled(self, paused: bool) -> None:
        if paused:
            self.__pause_action.setIcon(QtGui.QIcon.fromTheme('media-playback-start'))
            self.__pause_action.setText("Resume")
        else:
            self.__pause_action.setIcon(QtGui.QIcon.fromTheme('media-playback-pause'))
            self.__pause_action.setText("Pause")

    def __clearClicked(self) -> None:
        while self.__events.rowCount() > 0:
            self.__events.removeRow(0)

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        midi_event_urid = 'http://noisicaa.odahoda.de/lv2/processor_midi_monitor#midi_event'
        if not self.__pause_action.isChecked() and midi_event_urid in msg:
            time_numerator, time_denominator, midi = msg[midi_event_urid]
            time = audioproc.MusicalTime(time_numerator, time_denominator)

            row = self.__events.rowCount()
            self.__events.insertRow(row)

            columns = ['-', '-', '-', '-', '-']

            if time.numerator >= 0:
                columns[0] = '%.3f' % float(time)

            status = midi[0] & 0xf0
            if 0x80 <= status <= 0xe0:
                status_name = {
                    0x80: "Note Off",
                    0x90: "Note On",
                    0xa0: "Aftertouch",
                    0xb0: "Control Change",
                    0xc0: "Program Change",
                    0xd0: "Channel Pressure",
                    0xe0: "Pitch Bend",
                }[status]
                columns[1] = status_name
                columns[2] = '%d' % ((midi[0] & 0x0f) + 1)

                if status in (0x80, 0x90, 0xa0):
                    columns[3] = '%s (%d)' % (value_types.MIDI_TO_NOTE[midi[1]], midi[1])
                    columns[4] = '%d' % midi[2]

                elif status == 0xe0:
                    value = ((midi[2] << 7) | midi[1]) - 0x2000
                    columns[3] = '%d' % value

                elif status == 0xc0:
                    columns[3] = '%d' % midi[1]

                else:
                    columns[3] = '%d' % midi[1]
                    columns[4] = '%d' % midi[2]

            else:
                columns[1] = '0x%02x' % midi[0]


            for col, text in enumerate(columns):
                item = QtWidgets.QTableWidgetItem(text)
                if col in (0, 3, 4):
                    item.setData(Qt.TextAlignmentRole, Qt.AlignRight | Qt.AlignVCenter)
                self.__events.setItem(row, col, item)

            while self.__events.rowCount() > 1000:
                self.__events.removeRow(0)

            self.__events.scrollToBottom()


class MidiMonitorNode(base_node.Node):
    has_window = True

    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.MidiMonitor), type(node).__name__
        self.__widget = None  # type: QtWidgets.QWidget
        self.__node = node  # type: model.MidiMonitor

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None

        body = MidiMonitorNodeWidget(
            node=self.__node,
            session_prefix='inline',
            context=self.context)
        self.add_cleanup_function(body.cleanup)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__widget = QtWidgets.QScrollArea()
        self.__widget.setWidgetResizable(True)
        self.__widget.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.__widget.setWidget(body)

        return self.__widget

    def createWindow(self, **kwargs: Any) -> QtWidgets.QWidget:
        window = QtWidgets.QDialog(**kwargs)
        window.setAttribute(Qt.WA_DeleteOnClose, False)
        window.setWindowTitle("MIDI Monitor")

        body = MidiMonitorNodeWidget(
            node=self.__node,
            session_prefix='window',
            context=self.context)
        self.add_cleanup_function(body.cleanup)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(body)
        window.setLayout(layout)

        return window
