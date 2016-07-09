#!/usr/bin/python3

import logging
import os.path
import enum

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from .dock_widget import DockWidget
from .instrument_library import InstrumentLibraryDialog
from ..constants import DATA_DIR
from . import ui_base
from . import model

logger = logging.getLogger(__name__)

class MuteButton(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent, checkable=True, autoRaise=True)

        self._muted_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-muted.svg'))
        self._not_muted_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-muted.svg'))

        self.setIcon(self._not_muted_icon)

    def setChecked(self, checked):
        if checked:
            self.setIcon(self._muted_icon)
        else:
            self.setIcon(self._not_muted_icon)
        super().setChecked(checked)


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

        self._listeners = []

        self._name = QtWidgets.QLineEdit(self)
        self._name.textEdited.connect(self.onNameEdited)

        self._muted = MuteButton(self)
        self._muted.toggled.connect(self.onMutedEdited)

        self._volume = QtWidgets.QDoubleSpinBox(
            self,
            suffix='%',
            minimum=0.0, maximum=1000.0, decimals=1,
            singleStep=5, accelerated=True)
        self._volume.valueChanged.connect(self.onVolumeEdited)

        self._select_instrument = QtWidgets.QToolButton(
            self,
            icon=QtGui.QIcon.fromTheme('document-open'),
            autoRaise=True)
        self._select_instrument.clicked.connect(self.onSelectInstrument)

        self._instrument = QtWidgets.QLineEdit(self, readOnly=True)

        self._transpose_octaves = QtWidgets.QSpinBox(
            self,
            suffix=' octaves',
            minimum=-4, maximum=4,
            singleStep=1)
        self._transpose_octaves.valueChanged.connect(self.onTransposeOctavesEdited)

        main_layout = QtWidgets.QFormLayout(spacing=1)
        main_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        main_layout.addRow("Name", self._name)

        volume_layout = QtWidgets.QHBoxLayout()
        volume_layout.addWidget(self._muted)
        volume_layout.addWidget(self._volume, 1)
        main_layout.addRow("Volume", volume_layout)

        instrument_layout = QtWidgets.QHBoxLayout()
        instrument_layout.addWidget(self._select_instrument)
        instrument_layout.addWidget(self._instrument, 1)
        main_layout.addRow("Instrument", instrument_layout)

        main_layout.addRow("Transpose", self._transpose_octaves)

        main_area = QtWidgets.QWidget(self)
        main_area.setLayout(main_layout)

        self._body = QtWidgets.QStackedWidget(self)
        self._body.addWidget(QtWidgets.QWidget(self))
        self._body.addWidget(main_area)
        self.setWidget(self._body)

        self._window.currentTrackChanged.connect(self.onCurrentTrackChanged)

    def onCurrentTrackChanged(self, track):
        if track is self._track:
            return

        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

        self._track = track
        if self._track:
            self._body.setCurrentIndex(1)
            self._name.setText(self._track.name)
            self._listeners.append(
                self._track.listeners.add('name', self.onNameChanged))

            if isinstance(self._track, model.ScoreTrack):
                self._volume.setVisible(True)
                self._volume.setValue(self._track.volume)
                self._volume.setEnabled(not self._track.muted)
                self._listeners.append(
                    self._track.listeners.add('volume', self.onVolumeChanged))

                self._muted.setVisible(True)
                self._muted.setChecked(self._track.muted)
                self._listeners.append(
                    self._track.listeners.add('muted', self.onMutedChanged))

                self._instrument.setVisible(True)
                if self._track.instrument is not None:
                    self._instrument.setText(self._track.instrument.name)
                else:
                    self._instrument.setText('---')
                self._listeners.append(
                    self._track.listeners.add(
                        'instrument', self.onInstrumentChanged))

                self._transpose_octaves.setVisible(True)
                self._transpose_octaves.setValue(self._track.transpose_octaves)
                self._listeners.append(
                    self._track.listeners.add(
                        'transpose_octaves', self.onTransposeOctavesChanged))
            else:
                self._volume.setVisible(False)
                self._muted.setVisible(False)
                self._instrument.setVisible(False)
                self._transpose_octaves.setVisible(False)
        else:
            self._body.setCurrentIndex(0)

    def onNameChanged(self, old_name, new_name):
        self._name.setText(new_name)

    def onNameEdited(self, name):
        if self._track is None:
            return

        if name != self._track.name:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties', name=name))

    def onVolumeChanged(self, old_volume, new_volume):
        self._volume.setValue(new_volume)

    def onVolumeEdited(self, volume):
        if self._track is None:
            return

        if volume != self._track.volume:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties', volume=volume))

    def onMutedChanged(self, old_value, new_value):
        self._muted.setChecked(new_value)
        self._volume.setEnabled(not new_value)

    def onMutedEdited(self, muted):
        if self._track is None:
            return

        if muted != self._track.muted:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties', muted=muted))

    def onInstrumentChanged(self, old_instrument, new_instrument):
        if new_instrument is not None:
            self._instrument.setText(new_instrument.name)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self):
        if self._track is None:
            return

        import random
        self.onInstrumentEdited(random.randint(0, 10))

        # dialog = InstrumentLibraryDialog(
        #     self, self.app, self.app.instrument_library)
        # dialog.instrumentChanged.connect(
        #     self.onInstrumentEdited)

        # dialog.setWindowTitle(
        #     "Select instrument for track '%s'" % self._track.name)
        # dialog.selectInstrument(self._track.instrument)
        # dialog.exec_()

    def onInstrumentEdited(self, instr):
        if self._track is None:
            return

        client = self.window.getCurrentProjectView().project_client
        if instr is None:
            self.call_async(client.send_command(
                self._track.id, 'ClearInstrument'))
        else:
            self.call_async(client.send_command(
                self._track.id, 'SetInstrument',
                instrument_type='SoundFontInstrument',
                instrument_args={
                    'name': 'random-%d' % instr,
                    'path': '/usr/share/sounds/sf2/FluidR3_GM.sf2',
                    'bank': 0,
                    'preset': instr}))

    def onTransposeOctavesChanged(
            self, old_transpose_octaves, new_transpose_octaves):
        self._transpose_octaves.setValue(new_transpose_octaves)

    def onTransposeOctavesEdited(self, transpose_octaves):
        if self._track is None:
            return

        if transpose_octaves != self._track.transpose_octaves:
            client = self.window.getCurrentProjectView().project_client
            self.call_async(client.send_command(
                self._track.id, 'UpdateTrackProperties',
                transpose_octaves=transpose_octaves))
