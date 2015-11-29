#!/usr/bin/python3

import logging
import os.path
import enum

from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal, QMargins, QAbstractListModel, QModelIndex
from PyQt5.QtGui import QIcon, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget,
    QToolButton,
    QHBoxLayout,
    QVBoxLayout,
    QListView,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)

from .dock_widget import DockWidget
from noisicaa.music import UpdateTrackProperties, AddTrack, RemoveTrack, MoveTrack
from ..constants import DATA_DIR


logger = logging.getLogger(__name__)

# TODO: add listeners for all tracks, emit dataChanged, when name, visible, muted
# changes.

class TracksModel(QAbstractListModel):
    def __init__(self, sheet, parent=None):
        super().__init__(parent)

        self._sheet = sheet
        self._project = sheet.project

        self._sheet.add_change_listener('tracks', self.onTracksChanged)

    def close(self):
        self._sheet.remove_change_listener('tracks', self.onTracksChanged)

    def onTracksChanged(self, action, *args):
        # This could probably be done more efficiently...
        self.dataChanged.emit(self.index(0),
                              self.index(self.rowCount(None) - 1))

    def rowCount(self, parent):
        return len(self._sheet.tracks)

    def index(self, row, column=0, parent=None):
        if 0 <= row < len(self._sheet.tracks):
            track = self._sheet.tracks[row]
            return self.createIndex(row, column, track)
        else:
            return QModelIndex()

    def parent(self, index):
        return QModelIndex()

    def flags(self, index):
        return super().flags(index) | Qt.ItemIsEditable

    def data(self, index, role):
        if not index.isValid():
            return None

        track = index.internalPointer()

        if role in (Qt.DisplayRole, Qt.EditRole):
            return track.name

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        if role != Qt.EditRole:
            return False

        track = index.internalPointer()
        self._project.dispatch_command(
            track.address,
            UpdateTrackProperties(name=value))
        self.dataChanged.emit(index, index)
        return True

    def headerData(self, section, orientation, role):
        return None

    def toggleTrackVisible(self, index):
        track = index.internalPointer()
        self._project.dispatch_command(
            track.address,
            UpdateTrackProperties(visible=not track.visible))
        self.dataChanged.emit(index, index)

    def toggleTrackMute(self, index):
        track = index.internalPointer()
        self._project.dispatch_command(
            track.address,
            UpdateTrackProperties(muted=not track.muted))
        self.dataChanged.emit(index, index)

    def addTrack(self, track_type):
        track_idx = self._project.dispatch_command(
            self._sheet.address,
            AddTrack(track_type=track_type))
        self.dataChanged.emit(self.index(track_idx),
                              self.index(self.rowCount(None) - 1))
        return track_idx

    def removeTrack(self, index):
        track = index.internalPointer()
        self._project.dispatch_command(
            self._sheet.address,
            RemoveTrack(track=track.index))
        self.dataChanged.emit(self.index(0),
                              self.index(self.rowCount(None) - 1))

    def moveTrack(self, index, direction):
        track = index.internalPointer()
        track_idx = self._project.dispatch_command(
            self._sheet.address,
            MoveTrack(track=track.index, direction=direction))
        self.dataChanged.emit(self.index(0),
                              self.index(self.rowCount(None) - 1))
        return track_idx


class TrackItemDelegate(QStyledItemDelegate):
    def __init__(self, parent = None):
        super().__init__(parent)

        self._visible_icon = QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-visible.svg'))
        self._not_visible_icon = QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-visible.svg'))

        self._muted_icon = QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-muted.svg'))
        self._not_muted_icon = QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-muted.svg'))

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size += QSize(2 * size.height() + 8, 0)
        return size

    def showIconRect(self, rect):
        return QRect(rect.x() + 4, rect.y() + 2,
                     rect.height() - 4, rect.height() - 4)

    def playIconRect(self, rect):
        return QRect(rect.x() + rect.height() + 6, rect.y() + 2,
                     rect.height() - 4, rect.height() - 4)

    def itemRect(self, rect):
        return QRect(
            rect.x() + 2 * rect.height() + 8, rect.y(),
            rect.width() - 2 * rect.height() + 8, rect.height())

    def paint(self, painter, option, index):
        track = index.internalPointer()

        icon_size = option.rect.height()
        icon_area_width = 2 * icon_size + 8

        painter.save()
        try:
            if track.visible:
                self._visible_icon.paint(painter, self.showIconRect(option.rect))
            else:
                self._not_visible_icon.paint(painter, self.showIconRect(option.rect))

            if track.muted:
                self._muted_icon.paint(painter, self.playIconRect(option.rect))
            else:
                self._not_muted_icon.paint(painter, self.playIconRect(option.rect))

        finally:
            painter.restore()

        main_option = QStyleOptionViewItem(option)
        main_option.rect = self.itemRect(option.rect)
        super().paint(painter, main_option, index)

    def updateEditorGeometry(self, editor, option, index):
        main_option = QStyleOptionViewItem(option)
        main_option.rect = self.itemRect(option.rect)
        return super().updateEditorGeometry(editor, main_option, index)


class TrackList(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._delegate = TrackItemDelegate()
        self.setItemDelegate(self._delegate)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.row() >= 0:
            rect = self.visualRect(index)
            if self._delegate.showIconRect(rect).contains(event.pos()):
                self.model().toggleTrackVisible(index)
            elif self._delegate.playIconRect(rect).contains(event.pos()):
                self.model().toggleTrackMute(index)

        return super().mousePressEvent(event)


class TracksDockWidget(DockWidget):
    def __init__(self, window):
        super().__init__(
            parent=window,
            identifier='tracks',
            title="Tracks",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True)

        self._window = window
        self._model = None
        self._tracks_list = TrackList(self)
        self._tracks_list.activated.connect(self.onCurrentChanged)

        self._add_button = QToolButton(
            icon=QIcon.fromTheme('list-add'),
            iconSize=QSize(16, 16),
            autoRaise=True)
        self._add_button.clicked.connect(self.onAddClicked)
        self._remove_button = QToolButton(
            icon=QIcon.fromTheme('list-remove'),
            iconSize=QSize(16, 16),
            autoRaise=True)
        self._remove_button.clicked.connect(self.onRemoveClicked)
        self._move_up_button = QToolButton(
            icon=QIcon.fromTheme('go-up'),
            iconSize=QSize(16, 16),
            autoRaise=True)
        self._move_up_button.clicked.connect(self.onMoveUpClicked)
        self._move_down_button = QToolButton(
            icon=QIcon.fromTheme('go-down'),
            iconSize=QSize(16, 16),
            autoRaise=True)
        self._move_down_button.clicked.connect(self.onMoveDownClicked)

        buttons_layout = QHBoxLayout(spacing=1)
        buttons_layout.addWidget(self._add_button)
        buttons_layout.addWidget(self._remove_button)
        buttons_layout.addWidget(self._move_up_button)
        buttons_layout.addWidget(self._move_down_button)
        buttons_layout.addStretch(1)

        main_layout = QVBoxLayout(spacing=1)
        main_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        main_layout.addWidget(self._tracks_list, 1)
        main_layout.addLayout(buttons_layout)

        main_area = QWidget()
        main_area.setLayout(main_layout)
        self.setWidget(main_area)

        self._window.currentSheetChanged.connect(self.onCurrentSheetChanged)

    def onCurrentSheetChanged(self, sheet):
        if self._model is not None:
            self._model.close()
            self._model = None
            self._tracks_list.setModel(None)

        if sheet is not None:
            self._model = TracksModel(sheet)
            self._tracks_list.setModel(self._model)
            # TODO: select current track of sheet
            self.onCurrentChanged(None)
            self._add_button.setEnabled(True)
        else:
            self._add_button.setEnabled(False)
            self._remove_button.setEnabled(False)
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)

    def onCurrentChanged(self, index):
        if index is not None and index.isValid():
            self._remove_button.setEnabled(True)
            self._move_up_button.setEnabled(index.row() > 0)
            self._move_down_button.setEnabled(
                index.row() < index.model().rowCount(None) - 1)
            self._window.currentTrackChanged.emit(index.internalPointer())
        else:
            self._remove_button.setEnabled(False)
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)
            self._window.currentTrackChanged.emit(None)

    def onAddClicked(self):
        if self._model is None:
            return

        # support selecting track type
        track_idx = self._model.addTrack('score')
        index = self._model.index(track_idx)
        self._tracks_list.setCurrentIndex(index)
        self.onCurrentChanged(index)

    def onRemoveClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        self._model.removeTrack(index)
        new_index = self._model.index(
            min(index.row(), index.model().rowCount(None) - 1))
        self._tracks_list.setCurrentIndex(new_index)
        self.onCurrentChanged(new_index)

    def onMoveUpClicked(self):
        if self._model is None:
            return

        track_idx = self._model.moveTrack(self._tracks_list.currentIndex(), -1)
        index = self._model.index(track_idx)
        self._tracks_list.setCurrentIndex(index)
        self.onCurrentChanged(index)

    def onMoveDownClicked(self):
        if self._model is None:
            return

        track_idx = self._model.moveTrack(self._tracks_list.currentIndex(), 1)
        index = self._model.index(track_idx)
        self._tracks_list.setCurrentIndex(index)
        self.onCurrentChanged(index)

