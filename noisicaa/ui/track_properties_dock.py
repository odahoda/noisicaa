#!/usr/bin/python3

import logging
import os.path
import enum

from PyQt5.QtCore import Qt, QSize, QRect, QMargins
from PyQt5.QtGui import QIcon, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget,
    QToolButton,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QListView,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QLineEdit,
    QStackedWidget,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QToolButton,
)

from .dock_widget import DockWidget
from .instrument_library import InstrumentLibraryDialog
from noisicaa.music import UpdateTrackProperties, AddTrack, RemoveTrack, MoveTrack, SetInstrument, ClearInstrument, ScoreTrack
from ..constants import DATA_DIR
from ..instr.library import SoundFontInstrument

logger = logging.getLogger(__name__)

class MuteButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent, checkable=True, autoRaise=True)

        self._muted_icon = QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-muted.svg'))
        self._not_muted_icon = QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-muted.svg'))

        self.setIcon(self._not_muted_icon)

    def setChecked(self, checked):
        if checked:
            self.setIcon(self._muted_icon)
        else:
            self.setIcon(self._not_muted_icon)
        super().setChecked(checked)


class TrackPropertiesDockWidget(DockWidget):
    def __init__(self, window):
        super().__init__(
            parent=window,
            identifier='track-properties',
            title="Track Properties",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True)

        self._window = window
        self._track = None

        self._name = QLineEdit(self)
        self._name.textEdited.connect(self.onNameEdited)

        self._muted = MuteButton(self)
        self._muted.toggled.connect(self.onMutedEdited)

        self._volume = QDoubleSpinBox(
            self,
            suffix='%',
            minimum=0.0, maximum=1000.0, decimals=1,
            singleStep=5, accelerated=True)
        self._volume.valueChanged.connect(self.onVolumeEdited)

        self._select_instrument = QToolButton(
            self,
            icon=QIcon.fromTheme('document-open'),
            autoRaise=True)
        self._select_instrument.clicked.connect(self.onSelectInstrument)

        self._instrument = QLineEdit(self, readOnly=True)

        self._transpose_octaves = QSpinBox(
            self,
            suffix=' octaves',
            minimum=-4, maximum=4,
            singleStep=1)
        self._transpose_octaves.valueChanged.connect(self.onTransposeOctavesEdited)

        main_layout = QFormLayout(spacing=1)
        main_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        main_layout.addRow("Name", self._name)

        volume_layout = QHBoxLayout()
        volume_layout.addWidget(self._muted)
        volume_layout.addWidget(self._volume, 1)
        main_layout.addRow("Volume", volume_layout)

        instrument_layout = QHBoxLayout()
        instrument_layout.addWidget(self._select_instrument)
        instrument_layout.addWidget(self._instrument, 1)
        main_layout.addRow("Instrument", instrument_layout)

        main_layout.addRow("Transpose", self._transpose_octaves)

        main_area = QWidget(self)
        main_area.setLayout(main_layout)

        self._body = QStackedWidget(self)
        self._body.addWidget(QWidget(self))
        self._body.addWidget(main_area)
        self.setWidget(self._body)

        self._window.currentTrackChanged.connect(self.onCurrentTrackChanged)

    def onCurrentTrackChanged(self, track):
        if self._track is not None:
            self._track.remove_change_listener('name', self.onNameChanged)

            if isinstance(self._track, ScoreTrack):
                self._track.remove_change_listener('volume', self.onVolumeChanged)
                self._track.remove_change_listener('muted', self.onMutedChanged)
                self._track.remove_change_listener('instrument',
                                                   self.onInstrumentChanged)
                self._track.remove_change_listener('transpose_octaves',
                                                   self.onTransposeOctavesChanged)

        self._track = track
        if self._track:
            self._body.setCurrentIndex(1)
            self._name.setText(self._track.name)
            self._track.add_change_listener('name', self.onNameChanged)

            if isinstance(self._track, ScoreTrack):
                self._volume.setVisible(True)
                self._volume.setValue(self._track.volume)
                self._volume.setEnabled(not self._track.muted)
                self._track.add_change_listener('volume', self.onVolumeChanged)

                self._muted.setVisible(True)
                self._muted.setChecked(self._track.muted)
                self._track.add_change_listener('muted', self.onMutedChanged)

                self._instrument.setVisible(True)
                if self._track.instrument is not None:
                    self._instrument.setText(self._track.instrument.name)
                else:
                    self._instrument.setText('---')
                self._track.add_change_listener('instrument',
                                                self.onInstrumentChanged)

                self._transpose_octaves.setVisible(True)
                self._transpose_octaves.setValue(self._track.transpose_octaves)
                self._track.add_change_listener('transpose_octaves',
                                                self.onTransposeOctavesChanged)
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
            self._track.project.dispatch_command(
                self._track.address,
                UpdateTrackProperties(name=name))

    def onVolumeChanged(self, old_volume, new_volume):
        self._volume.setValue(new_volume)

    def onVolumeEdited(self, volume):
        if self._track is None:
            return

        if volume != self._track.volume:
            self._track.project.dispatch_command(
                self._track.address,
                UpdateTrackProperties(volume=volume))

    def onMutedChanged(self, old_value, new_value):
        self._muted.setChecked(new_value)
        self._volume.setEnabled(not new_value)

    def onMutedEdited(self, muted):
        if self._track is None:
            return

        if muted != self._track.muted:
            self._track.project.dispatch_command(
                self._track.address,
                UpdateTrackProperties(muted=muted))

    def onInstrumentChanged(self, old_instrument, new_instrument):
        if new_instrument is not None:
            self._instrument.setText(new_instrument.name)
        else:
            self._instrument.setText('---')

    def onSelectInstrument(self):
        if self._track is None:
            return

        dialog = InstrumentLibraryDialog(
            self, self._window._app, self._window._app.instrument_library)
        dialog.instrumentChanged.connect(
            self.onInstrumentEdited)

        dialog.setWindowTitle(
            "Select instrument for track '%s'" % self._track.name)
        dialog.selectInstrument(self._track.instrument)
        dialog.exec_()

    def onInstrumentEdited(self, instr):
        if self._track is None:
            return

        if instr is None:
            self._track.project.dispatch_command(
                self._track.address, ClearInstrument())
        else:
            self._track.project.dispatch_command(
                self._track.address,
                SetInstrument(instr=instr.to_json()))

    def onTransposeOctavesChanged(
            self, old_transpose_octaves, new_transpose_octaves):
        self._transpose_octaves.setValue(new_transpose_octaves)

    def onTransposeOctavesEdited(self, transpose_octaves):
        if self._track is None:
            return

        if transpose_octaves != self._track.transpose_octaves:
            self._track.project.dispatch_command(
                self._track.address,
                UpdateTrackProperties(transpose_octaves=transpose_octaves))
