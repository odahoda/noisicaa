#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from .dock_widget import DockWidget
from . import instrument_library
from . import ui_base
from noisicaa.music import model
from . import mute_button

logger = logging.getLogger(__name__)


class TrackProperties(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, track, **kwargs):
        super().__init__(**kwargs)

        self._track = track

        self._listeners = []

        self._name = QtWidgets.QLineEdit(self)
        self._name.textEdited.connect(self.onNameEdited)
        self._name.setText(self._track.name)
        self._listeners.append(
            self._track.listeners.add('name', self.onNameChanged))

        self._muted = mute_button.MuteButton(self)
        self._muted.toggled.connect(self.onMutedEdited)
        self._muted.setChecked(self._track.muted)
        self._listeners.append(
            self._track.listeners.add('muted', self.onMutedChanged))

        self._gain = QtWidgets.QDoubleSpinBox(
            self,
            suffix='dB',
            minimum=-80.0, maximum=20.0, decimals=1,
            singleStep=0.1, accelerated=True)
        self._gain.valueChanged.connect(self.onGainEdited)
        self._gain.setVisible(True)
        self._gain.setValue(self._track.gain)
        self._gain.setEnabled(not self._track.muted)
        self._listeners.append(
            self._track.listeners.add('gain', self.onGainChanged))

        self._form_layout = QtWidgets.QFormLayout(spacing=1)
        self._form_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self._form_layout.addRow("Name", self._name)

        gain_layout = QtWidgets.QHBoxLayout()
        gain_layout.addWidget(self._muted)
        gain_layout.addWidget(self._gain, 1)
        self._form_layout.addRow("Gain", gain_layout)

        self._pan = QtWidgets.QDoubleSpinBox(
            self,
            minimum=-1.0, maximum=1.0, decimals=2,
            singleStep=0.1, accelerated=True)
        self._pan.valueChanged.connect(self.onPanEdited)
        self._pan.setVisible(True)
        self._pan.setValue(self._track.pan)
        self._listeners.append(
            self._track.listeners.add('pan', self.onPanChanged))

        self._form_layout = QtWidgets.QFormLayout(spacing=1)
        self._form_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self._form_layout.addRow("Name", self._name)

        gain_layout = QtWidgets.QHBoxLayout()
        gain_layout.addWidget(self._muted)
        gain_layout.addWidget(self._gain, 1)
        self._form_layout.addRow("Gain", gain_layout)

        self._form_layout.addRow("Pan", self._pan)

        self.setLayout(self._form_layout)

    def cleanup(self):
        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    def onNameChanged(self, old_name, new_name):
        self._name.setText(new_name)

    def onNameEdited(self, name):
        if name != self._track.name:
            self.send_command_async(
                self._track.id, 'UpdateTrackProperties', name=name)

    def onGainChanged(self, old_gain, new_gain):
        self._gain.setValue(new_gain)

    def onGainEdited(self, gain):
        if gain != self._track.gain:
            self.send_command_async(
                self._track.id, 'UpdateTrackProperties', gain=gain)

    def onMutedChanged(self, old_value, new_value):
        self._muted.setChecked(new_value)
        self._gain.setEnabled(not new_value)

    def onMutedEdited(self, muted):
        if muted != self._track.muted:
            self.send_command_async(
                self._track.id, 'UpdateTrackProperties', muted=muted)

    def onPanChanged(self, old_value, new_value):
        self._pan.setValue(new_value)

    def onPanEdited(self, value):
        if value != self._track.pan:
            self.send_command_async(
                self._track.id, 'UpdateTrackProperties', pan=value)


class TrackGroupProperties(TrackProperties):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ControlTrackProperties(TrackProperties):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class SampleTrackProperties(TrackProperties):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ScoreTrackProperties(TrackProperties):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._select_instrument = QtWidgets.QToolButton(
            self,
            icon=QtGui.QIcon.fromTheme('document-open'),
            autoRaise=True)
        self._select_instrument.clicked.connect(self.onSelectInstrument)

        self._instrument = QtWidgets.QLineEdit(self, readOnly=True)
        if self._track.instrument is not None:
            self._instrument.setText(self._track.instrument)
        else:
            self._instrument.setText('---')
        self._listeners.append(
            self._track.listeners.add(
                'instrument', self.onInstrumentChanged))

        self._transpose_octaves = QtWidgets.QSpinBox(
            self,
            suffix=' octaves',
            minimum=-4, maximum=4,
            singleStep=1)
        self._transpose_octaves.valueChanged.connect(
            self.onTransposeOctavesEdited)
        self._transpose_octaves.setVisible(True)
        self._transpose_octaves.setValue(self._track.transpose_octaves)
        self._listeners.append(
            self._track.listeners.add(
                'transpose_octaves', self.onTransposeOctavesChanged))

        instrument_layout = QtWidgets.QHBoxLayout()
        instrument_layout.addWidget(self._select_instrument)
        instrument_layout.addWidget(self._instrument, 1)
        self._form_layout.addRow("Instrument", instrument_layout)

        self._form_layout.addRow("Transpose", self._transpose_octaves)

    def onInstrumentChanged(self, old_instrument, new_instrument):
        if new_instrument is not None:
            self._instrument.setText(new_instrument)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self):
        self.call_async(self.onSelectInstrumentAsync())

    async def onSelectInstrumentAsync(self):
        dialog = instrument_library.InstrumentLibraryDialog(
            **self.context_args, selectButton=True, parent=self)
        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.setModal(True)
        dialog.finished.connect(
            lambda _: self.onSelectInstrumentClosed(dialog))
        await dialog.setup()
        if self._track.instrument is not None:
            dialog.selectInstrument(self._track.instrument)
        dialog.show()

    def onSelectInstrumentClosed(self, dialog):
        if dialog.result() == dialog.Accepted:
            self.onInstrumentEdited(dialog.instrument())
        self.call_async(dialog.cleanup())

    def onInstrumentEdited(self, description):
        if description is None:
            return

        self.send_command_async(
            self._track.id, 'SetInstrument',
            instrument=description.uri)

    def onTransposeOctavesChanged(
            self, old_transpose_octaves, new_transpose_octaves):
        self._transpose_octaves.setValue(new_transpose_octaves)

    def onTransposeOctavesEdited(self, transpose_octaves):
        if transpose_octaves != self._track.transpose_octaves:
            self.send_command_async(
                self._track.id, 'UpdateTrackProperties',
                transpose_octaves=transpose_octaves)


class BeatTrackProperties(TrackProperties):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._select_instrument = QtWidgets.QToolButton(
            self,
            icon=QtGui.QIcon.fromTheme('document-open'),
            autoRaise=True)
        self._select_instrument.clicked.connect(self.onSelectInstrument)

        self._instrument = QtWidgets.QLineEdit(self, readOnly=True)
        if self._track.instrument is not None:
            self._instrument.setText(self._track.instrument)
        else:
            self._instrument.setText('---')
        self._listeners.append(
            self._track.listeners.add(
                'instrument', self.onInstrumentChanged))

        self._pitch = QtWidgets.QLineEdit(self)
        self._pitch.setText(str(self._track.pitch))
        self._pitch.editingFinished.connect(self.onPitchEdited)
        self._listeners.append(
            self._track.listeners.add(
                'pitch', self.onPitchChanged))

        instrument_layout = QtWidgets.QHBoxLayout()
        instrument_layout.addWidget(self._select_instrument)
        instrument_layout.addWidget(self._instrument, 1)
        self._form_layout.addRow("Instrument", instrument_layout)
        self._form_layout.addRow("Pitch", self._pitch)

    def onInstrumentChanged(self, old_instrument, new_instrument):
        if new_instrument is not None:
            self._instrument.setText(new_instrument)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self):
        if self._track is None:
            return

        self.call_async(self.onSelectInstrumentAsync())

    async def onSelectInstrumentAsync(self):
        dialog = instrument_library.InstrumentLibraryDialog(
            **self.context_args, selectButton=True, parent=self)
        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.setModal(True)
        dialog.finished.connect(
            lambda _: self.onSelectInstrumentClosed(dialog))
        await dialog.setup()
        if self._track.instrument is not None:
            dialog.selectInstrument(self._track.instrument)
        dialog.show()

    def onSelectInstrumentClosed(self, dialog):
        if dialog.result() == dialog.Accepted:
            self.onInstrumentEdited(dialog.instrument())
        self.call_async(dialog.cleanup())

    def onInstrumentEdited(self, description):
        if description is None:
            return

        self.send_command_async(
            self._track.id, 'SetBeatTrackInstrument',
            instrument=description.uri)

    def onPitchChanged(self, old_value, new_value):
        self._pitch.setText(str(new_value))

    def onPitchEdited(self):
        try:
            pitch = music.Pitch(self._pitch.text())
        except ValueError:
            self._pitch.setText(str(self._track.pitch))
        else:
            if pitch != self._track.pitch:
                self.send_command_async(
                    self._track.id, 'SetBeatTrackPitch', pitch=pitch)


class TrackPropertiesDockWidget(ui_base.ProjectMixin, DockWidget):
    def __init__(self, **kwargs):
        super().__init__(
            identifier='track-properties',
            title="Track Properties",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._track = None

    def setTrack(self, track):
        if track is self._track:
            return

        self._track = track
        if self._track is None:
            if self.main_widget is not None:
                self.main_widget.cleanup()
            self.setWidget(None)

        elif isinstance(self._track, model.TrackGroup):
            self.setWidget(TrackGroupProperties(
                track=self._track, **self.context_args))

        elif isinstance(self._track, model.ScoreTrack):
            self.setWidget(ScoreTrackProperties(
                track=self._track, **self.context_args))

        elif isinstance(self._track, model.BeatTrack):
            self.setWidget(BeatTrackProperties(
                track=self._track, **self.context_args))

        elif isinstance(self._track, model.ControlTrack):
            self.setWidget(ControlTrackProperties(
                track=self._track, **self.context_args))

        elif isinstance(self._track, model.SampleTrack):
            self.setWidget(SampleTrackProperties(
                track=self._track, **self.context_args))

        else:
            raise ValueError(type(self._track))
