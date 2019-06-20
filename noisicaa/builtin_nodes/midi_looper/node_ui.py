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

import enum
import logging
from typing import Any, Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import audioproc
from noisicaa import music
from noisicaa import value_types
from noisicaa.ui import ui_base
from noisicaa.ui import pianoroll
from noisicaa.ui import slots
from noisicaa.ui.graph import base_node
from noisicaa.builtin_nodes import processor_message_registry_pb2
from . import model

logger = logging.getLogger(__name__)


# Keep this in sync with ProcessorMidiLooper::RecordState in processor.h
class RecordState(enum.IntEnum):
    UNSET = 0
    OFF = 1
    WAITING = 2
    RECORDING = 3


class RecordButton(slots.SlotContainer, QtWidgets.QPushButton):
    recordState, setRecordState, recordStateChanged = slots.slot(RecordState, 'recordState')

    def __init__(self) -> None:
        super().__init__()

        self.setText("Record")
        self.setIcon(QtGui.QIcon.fromTheme('media-record'))

        self.__default_bg = self.palette().color(QtGui.QPalette.Button)

        self.recordStateChanged.connect(self.__recordStateChanged)

        self.__timer = QtCore.QTimer()
        self.__timer.setInterval(250)
        self.__timer.timeout.connect(self.__blink)
        self.__blink_state = False

    def __recordStateChanged(self, state: RecordState) -> None:
        palette = self.palette()
        if state == RecordState.OFF:
            self.__timer.stop()
            palette.setColor(self.backgroundRole(), self.__default_bg)
        elif state == RecordState.WAITING:
            self.__timer.start()
            self.__blink_state = True
            palette.setColor(self.backgroundRole(), QtGui.QColor(0, 255, 0))
        elif state == RecordState.RECORDING:
            self.__timer.stop()
            palette.setColor(self.backgroundRole(), QtGui.QColor(255, 0, 0))
        self.setPalette(palette)

    def __blink(self) -> None:
        self.__blink_state = not self.__blink_state
        palette = self.palette()
        if self.__blink_state:
            palette.setColor(self.backgroundRole(), QtGui.QColor(0, 255, 0))
        else:
            palette.setColor(self.backgroundRole(), self.__default_bg)
        self.setPalette(palette)


class MidiLooperNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QScrollArea):
    def __init__(self, node: model.MidiLooper, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__listeners['node-messages'] = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.__event_map = []  # type: List[int]
        self.__recorded_events = []  # type: List[value_types.MidiEvent]

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

        self.__record = RecordButton()
        self.__record.clicked.connect(self.__recordClicked)

        self.__pianoroll = pianoroll.PianoRoll()
        self.__pianoroll.setDuration(self.__node.duration)

        for event in self.__node.patches[0].events:
            self.__event_map.append(self.__pianoroll.addEvent(event))
        self.__listeners['events'] = self.__node.patches[0].events_changed.add(
            self.__eventsChanged)

        l2 = QtWidgets.QHBoxLayout()
        l2.addWidget(self.__record)
        l2.addWidget(self.__duration)
        l2.addStretch(1)

        l1 = QtWidgets.QVBoxLayout()
        l1.addLayout(l2)
        l1.addWidget(self.__pianoroll)
        body.setLayout(l1)

    def __eventsChanged(self, change: music.PropertyListChange[value_types.MidiEvent]) -> None:
        if isinstance(change, music.PropertyListInsert):
            event_id = self.__pianoroll.addEvent(change.new_value)
            self.__event_map.insert(change.index, event_id)

        elif isinstance(change, music.PropertyListDelete):
            event_id = self.__event_map.pop(change.index)
            self.__pianoroll.removeEvent(event_id)

        else:
            raise TypeError(type(change))

    def __durationChanged(self, change: music.PropertyValueChange[audioproc.MusicalDuration]) -> None:
        num_beats = change.new_value / audioproc.MusicalDuration(1, 4)
        assert num_beats.denominator == 1
        self.__duration.setValue(num_beats.numerator)
        self.__pianoroll.setDuration(change.new_value)

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
            self.__pianoroll.setPlaybackPosition(current_position)

        record_state_urid = 'http://noisicaa.odahoda.de/lv2/processor_midi_looper#record_state'
        if record_state_urid in msg:
            record_state = RecordState(msg[record_state_urid])
            self.__record.setRecordState(record_state)
            if record_state == RecordState.RECORDING:
                self.__recorded_events.clear()
                self.__pianoroll.clearEvents()
                self.__pianoroll.setUnfinishedNoteMode(pianoroll.UnfinishedNoteMode.ToPlaybackPosition)
            else:
                if record_state == RecordState.OFF:
                    del self.__listeners['events']

                    with self.project.apply_mutations('%s: Record patch' % self.__node.name):
                        patch = self.__node.patches[0]
                        patch.set_events(self.__recorded_events)
                        self.__recorded_events.clear()

                    self.__pianoroll.clearEvents()
                    self.__event_map.clear()
                    for event in self.__node.patches[0].events:
                        self.__event_map.append(self.__pianoroll.addEvent(event))
                    self.__listeners['events'] = self.__node.patches[0].events_changed.add(
                        self.__eventsChanged)

                self.__pianoroll.setUnfinishedNoteMode(pianoroll.UnfinishedNoteMode.ToEnd)


        recorded_event_urid = 'http://noisicaa.odahoda.de/lv2/processor_midi_looper#recorded_event'
        if recorded_event_urid in msg:
            time_numerator, time_denominator, midi, recorded = msg[recorded_event_urid]
            time = audioproc.MusicalTime(time_numerator, time_denominator)

            if recorded:
                event = value_types.MidiEvent(time, midi)
                self.__recorded_events.append(event)
                self.__pianoroll.addEvent(event)

            if midi[0] & 0xf0 == 0x90:
                self.__pianoroll.noteOn(midi[1])
            elif midi[0] & 0xf0 == 0x80:
                self.__pianoroll.noteOff(midi[1])


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
