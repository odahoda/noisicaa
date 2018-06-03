#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import Any, List  # pylint: disable=unused-import
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core  # pylint: disable=unused-import
from noisicaa import model
from noisicaa import music
from noisicaa import instrument_db
from .dock_widget import DockWidget
from . import instrument_library
from . import ui_base
from . import mute_button

logger = logging.getLogger(__name__)


class TrackProperties(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, track: music.Track, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._track = track

        self._listeners = []  # type: List[core.Listener]

        self._name = QtWidgets.QLineEdit(self)
        self._name.textEdited.connect(self.onNameEdited)
        self._name.setText(self._track.name)
        self._listeners.append(self._track.name_changed.add(self.onNameChanged))

        self._muted = mute_button.MuteButton(self)
        self._muted.toggled.connect(self.onMutedEdited)
        self._muted.setChecked(self._track.muted)
        self._listeners.append(self._track.muted_changed.add(self.onMutedChanged))

        self._gain = QtWidgets.QDoubleSpinBox(self)
        self._gain.setSuffix('dB')
        self._gain.setRange(-80.0, 20.0)
        self._gain.setDecimals(1)
        self._gain.setSingleStep(0.1)
        self._gain.setAccelerated(True)
        self._gain.valueChanged.connect(self.onGainEdited)
        self._gain.setVisible(True)
        self._gain.setValue(self._track.gain)
        self._gain.setEnabled(not self._track.muted)
        self._listeners.append(self._track.gain_changed.add(self.onGainChanged))

        self._pan = QtWidgets.QDoubleSpinBox(self)
        self._pan.setRange(-1.0, 1.0)
        self._pan.setDecimals(2)
        self._pan.setSingleStep(0.1)
        self._pan.setAccelerated(True)
        self._pan.valueChanged.connect(self.onPanEdited)
        self._pan.setVisible(True)
        self._pan.setValue(self._track.pan)
        self._listeners.append(self._track.pan_changed.add(self.onPanChanged))

        self._form_layout = QtWidgets.QFormLayout()
        self._form_layout.setSpacing(1)
        self._form_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self._form_layout.addRow("Name", self._name)

        gain_layout = QtWidgets.QHBoxLayout()
        gain_layout.addWidget(self._muted)
        gain_layout.addWidget(self._gain, 1)
        self._form_layout.addRow("Gain", gain_layout)

        self._form_layout.addRow("Pan", self._pan)

        self.setLayout(self._form_layout)

    def cleanup(self) -> None:
        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    def onNameChanged(self, change: model.PropertyValueChange[str]) -> None:
        self._name.setText(change.new_value)

    def onNameEdited(self, name: str) -> None:
        if name != self._track.name:
            self.send_command_async(music.Command(
                target=self._track.id,
                update_track_properties=music.UpdateTrackProperties(name=name)))

    def onGainChanged(self, change: model.PropertyValueChange[float]) -> None:
        self._gain.setValue(change.new_value)

    def onGainEdited(self, gain: float) -> None:
        if gain != self._track.gain:
            self.send_command_async(music.Command(
                target=self._track.id,
                update_track_properties=music.UpdateTrackProperties(gain=gain)))

    def onMutedChanged(self, change: model.PropertyValueChange[bool]) -> None:
        self._muted.setChecked(change.new_value)
        self._gain.setEnabled(not change.new_value)

    def onMutedEdited(self, muted: bool) -> None:
        if muted != self._track.muted:
            self.send_command_async(music.Command(
                target=self._track.id,
                update_track_properties=music.UpdateTrackProperties(muted=muted)))

    def onPanChanged(self, change: model.PropertyValueChange[float]) -> None:
        self._pan.setValue(change.new_value)

    def onPanEdited(self, value: float) -> None:
        if value != self._track.pan:
            self.send_command_async(music.Command(
                target=self._track.id,
                update_track_properties=music.UpdateTrackProperties(pan=value)))


class TrackGroupProperties(TrackProperties):
    pass

class ControlTrackProperties(TrackProperties):
    _track = None  # type: music.ControlTrack


class SampleTrackProperties(TrackProperties):
    _track = None  # type: music.SampleTrack


class ScoreTrackProperties(TrackProperties):
    _track = None  # type: music.ScoreTrack

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._select_instrument = QtWidgets.QToolButton(self)
        self._select_instrument.setIcon(QtGui.QIcon.fromTheme('document-open'))
        self._select_instrument.setAutoRaise(True)
        self._select_instrument.clicked.connect(self.onSelectInstrument)

        self._instrument = QtWidgets.QLineEdit(self)
        self._instrument.setReadOnly(True)
        if self._track.instrument is not None:
            self._instrument.setText(self._track.instrument)
        else:
            self._instrument.setText('---')
        self._listeners.append(self._track.instrument_changed.add(self.onInstrumentChanged))

        self._transpose_octaves = QtWidgets.QSpinBox(self)
        self._transpose_octaves.setSuffix(' octaves')
        self._transpose_octaves.setRange(-4, 4)
        self._transpose_octaves.setSingleStep(1)
        self._transpose_octaves.valueChanged.connect(self.onTransposeOctavesEdited)
        self._transpose_octaves.setVisible(True)
        self._transpose_octaves.setValue(self._track.transpose_octaves)
        self._listeners.append(
            self._track.transpose_octaves_changed.add(self.onTransposeOctavesChanged))

        instrument_layout = QtWidgets.QHBoxLayout()
        instrument_layout.addWidget(self._select_instrument)
        instrument_layout.addWidget(self._instrument, 1)
        self._form_layout.addRow("Instrument", instrument_layout)

        self._form_layout.addRow("Transpose", self._transpose_octaves)

    def onInstrumentChanged(self, change: model.PropertyValueChange[str]) -> None:
        if change.new_value is not None:
            self._instrument.setText(change.new_value)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self) -> None:
        self.call_async(self.onSelectInstrumentAsync())

    async def onSelectInstrumentAsync(self) -> None:
        dialog = instrument_library.InstrumentLibraryDialog(
            context=self.context, selectButton=True, parent=self)
        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.setModal(True)
        dialog.finished.connect(
            lambda _: self.onSelectInstrumentClosed(dialog))
        await dialog.setup()
        if self._track.instrument is not None:
            dialog.selectInstrument(self._track.instrument)
        dialog.show()

    def onSelectInstrumentClosed(
            self, dialog: instrument_library.InstrumentLibraryDialog) -> None:
        if dialog.result() == dialog.Accepted:
            self.onInstrumentEdited(dialog.instrument())
        self.call_async(dialog.cleanup())

    def onInstrumentEdited(self, description: instrument_db.InstrumentDescription) -> None:
        if description is None:
            return

        self.send_command_async(music.Command(
            target=self._track.id,
            set_instrument=music.SetInstrument(instrument=description.uri)))

    def onTransposeOctavesChanged(self, change: model.PropertyValueChange[int]) -> None:
        self._transpose_octaves.setValue(change.new_value)

    def onTransposeOctavesEdited(self, transpose_octaves: int) -> None:
        if transpose_octaves != self._track.transpose_octaves:
            self.send_command_async(music.Command(
                target=self._track.id,
                update_track_properties=music.UpdateTrackProperties(
                    transpose_octaves=transpose_octaves)))


class BeatTrackProperties(TrackProperties):
    _track = None  # type: music.BeatTrack

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._select_instrument = QtWidgets.QToolButton(
            self,
            icon=QtGui.QIcon.fromTheme('document-open'),
            autoRaise=True)
        self._select_instrument.clicked.connect(self.onSelectInstrument)

        self._instrument = QtWidgets.QLineEdit(self)
        self._instrument.setReadOnly(True)
        if self._track.instrument is not None:
            self._instrument.setText(self._track.instrument)
        else:
            self._instrument.setText('---')
        self._listeners.append(self._track.instrument_changed.add(self.onInstrumentChanged))

        self._pitch = QtWidgets.QLineEdit(self)
        self._pitch.setText(str(self._track.pitch))
        self._pitch.editingFinished.connect(self.onPitchEdited)
        self._listeners.append(self._track.pitch_changed.add(self.onPitchChanged))

        instrument_layout = QtWidgets.QHBoxLayout()
        instrument_layout.addWidget(self._select_instrument)
        instrument_layout.addWidget(self._instrument, 1)
        self._form_layout.addRow("Instrument", instrument_layout)
        self._form_layout.addRow("Pitch", self._pitch)

    def onInstrumentChanged(self, change: model.PropertyValueChange[str]) -> None:
        if change.new_value is not None:
            self._instrument.setText(change.new_value)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self) -> None:
        if self._track is None:
            return

        self.call_async(self.onSelectInstrumentAsync())

    async def onSelectInstrumentAsync(self) -> None:
        dialog = instrument_library.InstrumentLibraryDialog(
            context=self.context, selectButton=True, parent=self)
        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.setModal(True)
        dialog.finished.connect(
            lambda _: self.onSelectInstrumentClosed(dialog))
        await dialog.setup()
        if self._track.instrument is not None:
            dialog.selectInstrument(self._track.instrument)
        dialog.show()

    def onSelectInstrumentClosed(self, dialog: instrument_library.InstrumentLibraryDialog) -> None:
        if dialog.result() == dialog.Accepted:
            self.onInstrumentEdited(dialog.instrument())
        self.call_async(dialog.cleanup())

    def onInstrumentEdited(self, description: instrument_db.InstrumentDescription) -> None:
        if description is None:
            return

        self.send_command_async(music.Command(
            target=self._track.id,
            set_beat_track_instrument=music.SetBeatTrackInstrument(
                instrument=description.uri)))

    def onPitchChanged(self, change: model.PropertyValueChange[model.Pitch]) -> None:
        self._pitch.setText(str(change.new_value))

    def onPitchEdited(self) -> None:
        try:
            pitch = model.Pitch(self._pitch.text())
        except ValueError:
            self._pitch.setText(str(self._track.pitch))
        else:
            if pitch != self._track.pitch:
                self.send_command_async(music.Command(
                    target=self._track.id,
                    set_beat_track_pitch=music.SetBeatTrackPitch(pitch=pitch.to_proto())))


class TrackPropertiesDockWidget(ui_base.ProjectMixin, DockWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            identifier='track-properties',
            title="Track Properties",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._track = None  # type: music.Track

    def setTrack(self, track: music.Track) -> None:
        if track is self._track:
            return

        self._track = track
        if self._track is None:
            if self.main_widget is not None:
                self.main_widget.cleanup()
            self.setWidget(None)

        elif isinstance(self._track, music.TrackGroup):
            self.setWidget(TrackGroupProperties(
                track=self._track, context=self.context))

        elif isinstance(self._track, music.ScoreTrack):
            self.setWidget(ScoreTrackProperties(
                track=self._track, context=self.context))

        elif isinstance(self._track, music.BeatTrack):
            self.setWidget(BeatTrackProperties(
                track=self._track, context=self.context))

        elif isinstance(self._track, music.ControlTrack):
            self.setWidget(ControlTrackProperties(
                track=self._track, context=self.context))

        elif isinstance(self._track, music.SampleTrack):
            self.setWidget(SampleTrackProperties(
                track=self._track, context=self.context))

        else:
            raise ValueError(type(self._track))
