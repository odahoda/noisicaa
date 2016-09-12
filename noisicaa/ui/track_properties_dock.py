#!/usr/bin/python3

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


class TrackProperties(ui_base.CommonMixin, QtWidgets.QWidget):
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

        self._volume = QtWidgets.QDoubleSpinBox(
            self,
            suffix='%',
            minimum=0.0, maximum=1000.0, decimals=1,
            singleStep=5, accelerated=True)
        self._volume.valueChanged.connect(self.onVolumeEdited)
        self._volume.setVisible(True)
        self._volume.setValue(self._track.volume)
        self._volume.setEnabled(not self._track.muted)
        self._listeners.append(
            self._track.listeners.add('volume', self.onVolumeChanged))

        self._form_layout = QtWidgets.QFormLayout(spacing=1)
        self._form_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self._form_layout.addRow("Name", self._name)

        volume_layout = QtWidgets.QHBoxLayout()
        volume_layout.addWidget(self._muted)
        volume_layout.addWidget(self._volume, 1)
        self._form_layout.addRow("Volume", volume_layout)

        self.setLayout(self._form_layout)

    def cleanup(self):
        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    def onNameChanged(self, old_name, new_name):
        self._name.setText(new_name)

    def onNameEdited(self, name):
        if name != self._track.name:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties', name=name))

    def onVolumeChanged(self, old_volume, new_volume):
        self._volume.setValue(new_volume)

    def onVolumeEdited(self, volume):
        if volume != self._track.volume:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties', volume=volume))

    def onMutedChanged(self, old_value, new_value):
        self._muted.setChecked(new_value)
        self._volume.setEnabled(not new_value)

    def onMutedEdited(self, muted):
        if muted != self._track.muted:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties', muted=muted))


class TrackGroupProperties(TrackProperties):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ControlTrackProperties(TrackProperties):
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
            self._instrument.setText(self._track.instrument.name)
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
            self._instrument.setText(new_instrument.name)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self):
        self.call_async(self.onSelectInstrumentAsync())

    async def onSelectInstrumentAsync(self):
        dialog = instrument_library.InstrumentLibraryDialog(
            **self.context, selectButton=True, parent=self)
        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.setModal(True)
        dialog.finished.connect(
            lambda _: self.onSelectInstrumentClosed(dialog))
        await dialog.setup()
        if self._track.instrument is not None:
            dialog.selectInstrument(self._track.instrument.library_id)
        dialog.show()

    def onSelectInstrumentClosed(self, dialog):
        if dialog.result() == dialog.Accepted:
            self.onInstrumentEdited(dialog.instrument())
        self.call_async(dialog.cleanup())

    def onInstrumentEdited(self, instr):
        client = self.window.getCurrentProjectView().project_client
        if instr is not None:
            self.call_async(client.send_command(
                self._track.id, 'SetInstrument',
                instrument_type='SoundFontInstrument',
                instrument_args={
                    'name': instr.name,
                    'library_id': instr.id,
                    'path': instr.path,
                    'bank': instr.bank,
                    'preset': instr.preset}))

    def onTransposeOctavesChanged(
            self, old_transpose_octaves, new_transpose_octaves):
        self._transpose_octaves.setValue(new_transpose_octaves)

    def onTransposeOctavesEdited(self, transpose_octaves):
        if transpose_octaves != self._track.transpose_octaves:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties',
                transpose_octaves=transpose_octaves))


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
            self._instrument.setText(self._track.instrument.name)
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
            self._instrument.setText(new_instrument.name)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self):
        if self._track is None:
            return

        self.call_async(self.onSelectInstrumentAsync())

    async def onSelectInstrumentAsync(self):
        dialog = instrument_library.InstrumentLibraryDialog(
            **self.context, selectButton=True, parent=self)
        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.setModal(True)
        dialog.finished.connect(
            lambda _: self.onSelectInstrumentClosed(dialog))
        await dialog.setup()
        if self._track.instrument is not None:
            dialog.selectInstrument(self._track.instrument.library_id)
        dialog.show()

    def onSelectInstrumentClosed(self, dialog):
        if dialog.result() == dialog.Accepted:
            self.onInstrumentEdited(dialog.instrument())
        self.call_async(dialog.cleanup())

    def onInstrumentEdited(self, instr):
        if instr is None:
            return

        client = self.window.getCurrentProjectView().project_client
        self.call_async(client.send_command(
            self._track.id, 'SetBeatTrackInstrument',
            instrument_type='SoundFontInstrument',
            instrument_args={
                'name': instr.name,
                'library_id': instr.id,
                'path': instr.path,
                'bank': instr.bank,
                'preset': instr.preset}))

    def onPitchChanged(self, old_value, new_value):
        self._pitch.setText(str(new_value))

    def onPitchEdited(self):
        try:
            pitch = music.Pitch(self._pitch.text())
        except ValueError:
            self._pitch.setText(str(self._track.pitch))
        else:
            if pitch != self._track.pitch:
                client = self.window.getCurrentProjectView().project_client
                self.call_async(client.send_command(
                    self._track.id, 'SetBeatTrackPitch', pitch=pitch))


class TrackPropertiesDockWidget(DockWidget):
    def __init__(self, app, window):
        super().__init__(
            app=app,
            parent=window,
            identifier='track-properties',
            title="Track Properties",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True)

        self._window = window
        self._track = None

        self._window.currentTrackChanged.connect(self.onCurrentTrackChanged)

    def onCurrentTrackChanged(self, track):
        if track is self._track:
            return

        self._track = track
        if self._track is None:
            if self.main_widget is not None:
                self.main_widget.cleanup()
            self.setWidget(None)

        elif isinstance(self._track, model.TrackGroup):
            self.setWidget(TrackGroupProperties(
                track=self._track, **self.context))

        elif isinstance(self._track, model.ScoreTrack):
            self.setWidget(ScoreTrackProperties(
                track=self._track, **self.context))

        elif isinstance(self._track, model.BeatTrack):
            self.setWidget(BeatTrackProperties(
                track=self._track, **self.context))

        elif isinstance(self._track, model.ControlTrack):
            self.setWidget(ControlTrackProperties(
                track=self._track, **self.context))

        else:
            raise ValueError(type(self._track))
