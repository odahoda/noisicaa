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
from noisicaa.music import model

logger = logging.getLogger(__name__)


class TracksModelItem(object):
    def __init__(self, track, parent):
        self.track = track
        self.parent = parent
        self.children = []
        self.listeners = []

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


class TracksModelImpl(QtCore.QAbstractItemModel):
    VisibleRole = Qt.UserRole
    MuteRole = Qt.UserRole + 1

    def __init__(self, sheet=None, **kwargs):
        super().__init__(**kwargs)

        self._sheet = sheet

        self._root_item = self._buildItem(self._sheet.master_group, None)

    def _buildItem(self, track, parent):
        item = TracksModelItem(track, parent)

        if isinstance(track, model.TrackGroup):
            for child_track in track.tracks:
                item.children.append(
                    self._buildItem(child_track, item))

            item.listeners.append(
                track.listeners.add(
                    'tracks',
                    functools.partial(self.onGroupChanged, item)))

        for prop in ('name', 'muted', 'visible'):
            item.listeners.append(
                track.listeners.add(
                    prop,
                    functools.partial(self.onTrackChanged, item, prop)))

        return item

    def close(self):
        for item in self._root_item.walk():
            for listener in item.listeners:
                listener.remove()
        self._root_item = None

    def onGroupChanged(self, group, action, *args):
        group_index = self.indexForItem(group)
        if action == 'insert':
            index, child = args
            self.beginInsertRows(group_index, index, index)
            group.children.insert(index, self._buildItem(child, group))
            self.endInsertRows()
        else:
            index, = args
            self.beginRemoveRows(group_index, index, index)
            del group.children[index]
            self.endRemoveRows()

    def onTrackChanged(self, item, prop, old, new):
        track = item.track
        logger.info(
            "Value of %s on track %s: %s->%s", prop, track.id, old, new)
        item_index = self.indexForItem(item)
        self.dataChanged.emit(item_index, item_index, [])

    def indexForItem(self, item):
        if item.parent is None:
            return self.createIndex(0, 0, item)
        else:
            return self.createIndex(
                item.parent.children.index(item), 0, item)

    def rowCount(self, parent):
        if parent.column() > 0:  # pragma: no coverage
            return 0

        if not parent.isValid():
            return 1

        parent_item = parent.internalPointer()
        return len(parent_item.children)

    def columnCount(self, parent):
        return 1

    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        if not parent.isValid():
            assert row == 0, row
            assert column == 0, column
            return self.createIndex(row, column, self._root_item)

        parent_item = parent.internalPointer()
        assert isinstance(parent_item.track, model.TrackGroup), parent_item.track

        item = parent_item.children[row]
        return self.createIndex(row, column, item)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        item = index.internalPointer()
        if item.parent is None:
            return QtCore.QModelIndex()

        return self.indexForItem(item.parent)

    def flags(self, index):
        return super().flags(index) | Qt.ItemIsEditable

    def data(self, index, role):
        if not index.isValid():  # pragma: no coverage
            return None

        item = index.internalPointer()
        track = item.track

        if role in (Qt.DisplayRole, Qt.EditRole):
            return track.name
        elif role == self.VisibleRole:
            return track.visible
        elif role == self.MuteRole:  # pragma: no branch
            return track.muted

        return None  # pragma: no coverage

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        item = index.internalPointer()
        track = item.track

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

    def headerData(self, section, orientation, role):  # pragma: no coverage
        return None

    async def addTrack(self, track_type, parent_index):
        if parent_index.isValid():
            parent_item = parent_index.internalPointer()
            parent_group = parent_item.track
            if not isinstance(parent_group, model.TrackGroup):
                parent_group = parent_group.parent
        else:
            parent_group = self._sheel_master_group

        assert isinstance(parent_group, model.TrackGroup)

        return await self.project_client.send_command(
            self._sheet.id, 'AddTrack',
            parent_group_id=parent_group.id,
            track_type=track_type)

    async def removeTrack(self, index):
        track = index.internalPointer().track
        return await self.project_client.send_command(
            self._sheet.id, 'RemoveTrack', track_id=track.id)

    async def moveTrack(self, index, direction):
        track = index.internalPointer().track
        return await self.project_client.send_command(
            self._sheet.id, 'MoveTrack', track=track.index, direction=direction)


class TracksModel(ui_base.ProjectMixin, TracksModelImpl):
    pass


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


class TrackList(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderHidden(True)
        self.setItemsExpandable(False)

        # self._delegate = TrackItemDelegate()
        # self.setItemDelegate(self._delegate)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        # if index.row() >= 0:
        #     rect = self.visualRect(index)
        #     model = self.model()
        #     if self._delegate.showIconRect(rect).contains(event.pos()):
        #         model.setData(
        #             index, not model.data(index, TracksModel.VisibleRole),
        #             TracksModel.VisibleRole)
        #         event.accept()
        #     elif self._delegate.playIconRect(rect).contains(event.pos()):
        #         model.setData(
        #             index, not model.data(index, TracksModel.MuteRole),
        #             TracksModel.MuteRole)
        #         event.accept()

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
            self._tracks_list.expandAll()
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
                index.row() < index.model().rowCount(QtCore.QModelIndex()) - 1)
            self._window.currentTrackChanged.emit(index.internalPointer().track)
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
            self._model.addTrack(
                track_type='score',
                parent_index=self._tracks_list.currentIndex()),
            callback=self.onAddTrackDone)

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
        pass
        # new_index = self._model.index(
        #     min(index.row(), self._model.rowCount(None) - 1))
        # self._tracks_list.setCurrentIndex(new_index)
        # self.onCurrentChanged(new_index)

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



