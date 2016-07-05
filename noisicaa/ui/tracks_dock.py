#!/usr/bin/python3

import functools
import logging
import os.path
import enum

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from .dock_widget import DockWidget
from ..constants import DATA_DIR
from . import ui_base

logger = logging.getLogger(__name__)

# TODO: add listeners for all tracks, emit dataChanged, when name, visible, muted
# changes.

class TracksModel(ui_base.ProjectMixin, QtCore.QAbstractListModel):
    VisibleRole = Qt.UserRole
    MuteRole = Qt.UserRole + 1

    def __init__(self, sheet=None, **kwargs):
        super().__init__(**kwargs)

        self._sheet = sheet
        self._tracks_listener = self._sheet.listeners.add(
            'tracks', self.onTracksChanged)

    def close(self):
        self._tracks_listener.remove()

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
            return QtCore.QModelIndex()

    def parent(self, index):
        return QtCore.QModelIndex()

    def flags(self, index):
        return super().flags(index) | Qt.ItemIsEditable

    def data(self, index, role):
        if not index.isValid():
            return None

        track = index.internalPointer()

        if role in (Qt.DisplayRole, Qt.EditRole):
            return track.name
        elif role == self.VisibleRole:
            return track.visible
        elif role == self.MuteRole:
            return track.muted

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        track = index.internalPointer()

        if role == Qt.EditRole:
            self.send_command_async(
                track.id, 'UpdateTrackProperties', name=value)
            return False
        elif role == self.VisibleRole:
            self.send_command_async(
                track.id, 'UpdateTrackProperties', visible=value)
            return False
        elif role == self.MuteRole:
            self.send_command_async(
                track.id, 'UpdateTrackProperties', muted=value)
            return False

        return False

    def headerData(self, section, orientation, role):
        return None

    async def addTrack(self, track_type):
        return await self.project_client.send_command(
            self._sheet.id, 'AddTrack', track_type=track_type)

    async def removeTrack(self, index):
        track = index.internalPointer()
        return await self.project_client.send_command(
            self._sheet.id, 'RemoveTrack', track=track.index)

    async def moveTrack(self, index, direction):
        track = index.internalPointer()
        return await self.project_client.send_command(
            self._sheet.id, 'MoveTrack', track=track.index, direction=direction)

class TrackItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent = None):
        super().__init__(parent)

        self._visible_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-visible.svg'))
        self._not_visible_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-visible.svg'))

        self._muted_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-muted.svg'))
        self._not_muted_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-muted.svg'))

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size += QtCore.QSize(2 * size.height() + 8, 0)
        return size

    def showIconRect(self, rect):
        return QtCore.QRect(rect.x() + 4, rect.y() + 2,
                     rect.height() - 4, rect.height() - 4)

    def playIconRect(self, rect):
        return QtCore.QRect(rect.x() + rect.height() + 6, rect.y() + 2,
                     rect.height() - 4, rect.height() - 4)

    def itemRect(self, rect):
        return QtCore.QRect(
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

        main_option = QtWidgets.QStyleOptionViewItem(option)
        main_option.rect = self.itemRect(option.rect)
        super().paint(painter, main_option, index)

    def updateEditorGeometry(self, editor, option, index):
        main_option = QtWidgets.QStyleOptionViewItem(option)
        main_option.rect = self.itemRect(option.rect)
        return super().updateEditorGeometry(editor, main_option, index)


class TrackList(QtWidgets.QListView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._delegate = TrackItemDelegate()
        self.setItemDelegate(self._delegate)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.row() >= 0:
            rect = self.visualRect(index)
            model = self.model()
            if self._delegate.showIconRect(rect).contains(event.pos()):
                model.setData(
                    index, not model.data(index, TracksModel.VisibleRole),
                    TracksModel.VisibleRole)
                event.accept()
            elif self._delegate.playIconRect(rect).contains(event.pos()):
                model.setData(
                    index, not model.data(index, TracksModel.MuteRole),
                    TracksModel.MuteRole)
                event.accept()

        return super().mousePressEvent(event)


class TracksDockWidget(DockWidget):
    def __init__(self, app, window):
        super().__init__(
            app=app,
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

        self._add_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('list-add'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._add_button.clicked.connect(self.onAddClicked)
        self._remove_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('list-remove'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._remove_button.clicked.connect(self.onRemoveClicked)
        self._move_up_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('go-up'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._move_up_button.clicked.connect(self.onMoveUpClicked)
        self._move_down_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('go-down'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._move_down_button.clicked.connect(self.onMoveDownClicked)

        buttons_layout = QtWidgets.QHBoxLayout(spacing=1)
        buttons_layout.addWidget(self._add_button)
        buttons_layout.addWidget(self._remove_button)
        buttons_layout.addWidget(self._move_up_button)
        buttons_layout.addWidget(self._move_down_button)
        buttons_layout.addStretch(1)

        main_layout = QtWidgets.QVBoxLayout(spacing=1)
        main_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        main_layout.addWidget(self._tracks_list, 1)
        main_layout.addLayout(buttons_layout)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(main_layout)
        self.setWidget(main_area)

        self._window.currentSheetChanged.connect(self.onCurrentSheetChanged)

    def onCurrentSheetChanged(self, sheet):
        if self._model is not None:
            self._model.close()
            self._model = None
            self._tracks_list.setModel(None)

        if sheet is not None:
            self._model = TracksModel(
                **self.window.getCurrentProjectView().context, sheet=sheet)
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

        # TODO: support selecting track type
        self.call_async(
            self._model.addTrack('score'), callback=self.onAddTrackDone)

    def onAddTrackDone(self, track_idx):
        index = self._model.index(track_idx)
        self._tracks_list.setCurrentIndex(index)
        self.onCurrentChanged(index)

    def onRemoveClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        self.call_async(
            self._model.removeTrack(index),
            callback=functools.partial(self.onRemoveTrackDone, index=index))

    def onRemoveTrackDone(self, result, index):
        new_index = self._model.index(
            min(index.row(), self._model.rowCount(None) - 1))
        self._tracks_list.setCurrentIndex(new_index)
        self.onCurrentChanged(new_index)

    def onMoveUpClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        self.call_async(
            self._model.moveTrack(index, -1), callback=self.onMoveTrackDone)

    def onMoveDownClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        self.call_async(
            self._model.moveTrack(index, 1), callback=self.onMoveTrackDone)

    def onMoveTrackDone(self, track_idx):
        index = self._model.index(track_idx)
        self._tracks_list.setCurrentIndex(index)
        self.onCurrentChanged(index)



