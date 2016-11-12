#!/usr/bin/python3

import functools
import logging
import os.path

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

    COLUMNS = 2

    def __init__(self, sheet=None, **kwargs):
        super().__init__(**kwargs)

        self._sheet = sheet

        self._root_item = self._buildItem(self._sheet.master_group, None)

        self._score_icon = QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-score.svg'))
        self._beat_icon = QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-beat.svg'))
        self._control_icon = QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-control.svg'))
        self._sample_icon = QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-sample.svg'))
        self._group_icon = QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-group.svg'))

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
        elif action == 'delete':
            index, child = args
            self.beginRemoveRows(group_index, index, index)
            del group.children[index]
            self.endRemoveRows()
        else:
            raise ValueError(action)

    def onTrackChanged(self, item, prop, old, new):
        track = item.track
        logger.info(
            "Value of %s on track %s: %s->%s", prop, track.id, old, new)
        self.dataChanged.emit(
            self.indexForItem(item, column=0),
            self.indexForItem(item, column=self.COLUMNS - 1),
            [])

    def track(self, index):
        if not index.isValid():
            raise ValueError("Invalid index")

        item = index.internalPointer()
        assert item is not None
        return item.track

    def indexForTrack(self, track):
        for item in self._root_item.walk():
            if item.track.id == track.id:
                return self.indexForItem(item)

        raise ValueError("Invalid track")

    def indexForItem(self, item, column=0):
        if item.parent is None:
            return self.createIndex(0, column, item)
        else:
            return self.createIndex(
                item.parent.children.index(item), column, item)

    def rowCount(self, parent):
        if parent.column() > 0:  # pragma: no coverage
            return 0

        if not parent.isValid():
            return 1

        parent_item = parent.internalPointer()
        if parent_item is None:
            return 0

        return len(parent_item.children)

    def columnCount(self, parent):
        return self.COLUMNS

    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        if not parent.isValid():
            assert row == 0, row
            return self.createIndex(row, column, self._root_item)

        parent_item = parent.internalPointer()
        assert isinstance(parent_item.track, model.TrackGroup), parent_item.track

        item = parent_item.children[row]
        return self.createIndex(row, column, item)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        item = index.internalPointer()
        if item is None or item.parent is None:
            return QtCore.QModelIndex()

        return self.indexForItem(item.parent)

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 0:
            flags |= Qt.ItemIsEditable
        return flags

    def data(self, index, role):
        if not index.isValid():  # pragma: no coverage
            return None

        item = index.internalPointer()
        if item is None:
            return None

        track = item.track

        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column() == 0:
                return track.name
        elif role == Qt.DecorationRole:
            if index.column() == 0:
                if isinstance(track, model.ScoreTrack):
                    return self._score_icon
                elif isinstance(track, model.BeatTrack):
                    return self._beat_icon
                elif isinstance(track, model.ControlTrack):
                    return self._control_icon
                elif isinstance(track, model.SampleTrack):
                    return self._sample_icon
                elif isinstance(track, model.TrackGroup):
                    return self._group_icon
                else:
                    return None
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
            if not isinstance(parent_item.track, model.TrackGroup):
                insert_index = parent_index.row() + 1
                parent_item = parent_item.parent
            else:
                insert_index = -1
        else:
            parent_item = self._root_item
            insert_index = -1

        parent_group = parent_item.track
        assert isinstance(parent_group, model.TrackGroup)

        list_index =  await self.project_client.send_command(
            self._sheet.id, 'AddTrack',
            parent_group_id=parent_group.id,
            insert_index=insert_index,
            track_type=track_type)

        return self.index(list_index, 0, self.indexForItem(parent_item))

    async def removeTrack(self, index):
        track = index.internalPointer().track
        return await self.project_client.send_command(
            self._sheet.id, 'RemoveTrack', track_id=track.id)


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
        if index.column() == 1:
            size = QtCore.QSize(2 * size.height() + 8, size.height())
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
        super().paint(painter, option, index)

        if index.column() == 1:
            track = index.internalPointer().track

            icon_size = option.rect.height()
            icon_area_width = 2 * icon_size + 8

            painter.save()
            try:
                if track.visible:
                    self._visible_icon.paint(
                        painter, self.showIconRect(option.rect))
                else:
                    self._not_visible_icon.paint(
                        painter, self.showIconRect(option.rect))

                if track.muted:
                    self._muted_icon.paint(
                        painter, self.playIconRect(option.rect))
                else:
                    self._not_muted_icon.paint(
                        painter, self.playIconRect(option.rect))

            finally:
                painter.restore()



class TrackList(QtWidgets.QTreeView):
    currentIndexChanged = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderHidden(True)
        self.setTreePosition(0)
        self.setExpandsOnDoubleClick(False)

        self._delegate = TrackItemDelegate()
        self.setItemDelegate(self._delegate)

    def setModel(self, model):
        super().setModel(model)
        if model is not None:
            self.expandAll()
            self.header().resizeSection(1, self.sizeHintForColumn(1))
            self.header().swapSections(0, 1)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid() and index.column() == 1:
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

    def currentChanged(self, current, previous):
        self.currentIndexChanged.emit(current)


class TracksDockWidget(ui_base.ProjectMixin, DockWidget):
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs):
        super().__init__(
            identifier='tracks',
            title="Tracks",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._model = None
        self._tracks_list = TrackList(self)
        self._tracks_list.currentIndexChanged.connect(
            self.onCurrentChanged)

        self._add_score_track_action = QtWidgets.QAction(
            QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-score.svg')),
            "Score track", self,
            triggered=functools.partial(self.onAddClicked, 'score'))
        self._add_beat_track_action = QtWidgets.QAction(
            QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-beat.svg')),
            "Beat track", self,
            triggered=functools.partial(self.onAddClicked, 'beat'))
        self._add_control_track_action = QtWidgets.QAction(
            QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-control.svg')),
            "Control track", self,
            triggered=functools.partial(self.onAddClicked, 'control'))
        self._add_sample_track_action = QtWidgets.QAction(
            QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-sample.svg')),
            "Sample track", self,
            triggered=functools.partial(self.onAddClicked, 'sample'))
        self._add_track_group_action = QtWidgets.QAction(
            QtGui.QIcon(
                os.path.join(DATA_DIR, 'icons', 'track-type-group.svg')),
            "Group", self,
            triggered=functools.partial(self.onAddClicked, 'group'))

        self._add_track_menu = QtWidgets.QMenu()
        self._add_track_menu.addAction(self._add_score_track_action)
        self._add_track_menu.addAction(self._add_beat_track_action)
        self._add_track_menu.addAction(self._add_control_track_action)
        self._add_track_menu.addAction(self._add_sample_track_action)
        self._add_track_menu.addAction(self._add_track_group_action)

        self._add_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('list-add'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._add_button.setMenu(self._add_track_menu)
        self._add_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

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

        self._move_left_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('go-previous'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._move_left_button.clicked.connect(self.onMoveLeftClicked)
        self._move_right_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('go-next'),
            iconSize=QtCore.QSize(16, 16),
            autoRaise=True)
        self._move_right_button.clicked.connect(self.onMoveRightClicked)

        buttons_layout = QtWidgets.QHBoxLayout(spacing=1)
        buttons_layout.addWidget(self._add_button)
        buttons_layout.addWidget(self._remove_button)
        buttons_layout.addWidget(self._move_up_button)
        buttons_layout.addWidget(self._move_down_button)
        buttons_layout.addWidget(self._move_left_button)
        buttons_layout.addWidget(self._move_right_button)
        buttons_layout.addStretch(1)

        main_layout = QtWidgets.QVBoxLayout(spacing=1)
        main_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        main_layout.addWidget(self._tracks_list, 1)
        main_layout.addLayout(buttons_layout)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(main_layout)
        self.setWidget(main_area)

    def setCurrentSheet(self, sheet):
        if self._model is not None:
            self._model.close()
            self._model = None
            self._tracks_list.setModel(None)

        if sheet is not None:
            self._model = TracksModel(sheet=sheet, **self.context)
            self._tracks_list.setModel(self._model)
            # TODO: select current track of sheet
            self.onCurrentChanged(None)
            self._add_button.setEnabled(True)
        else:
            self._add_button.setEnabled(False)
            self._remove_button.setEnabled(False)
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)

    def onCurrentChanged(self, index, previous=None):
        if index is not None and index.isValid():
            track = self._model.track(index)
            self._remove_button.setEnabled(not track.is_master_group)
            self._move_up_button.setEnabled(
                not track.is_master_group and not track.is_first)
            self._move_down_button.setEnabled(
                not track.is_master_group and not track.is_last)
            self._move_left_button.setEnabled(
                not track.is_master_group and not track.parent.is_master_group)
            self._move_right_button.setEnabled(
                not track.is_master_group and not track.is_first
                and isinstance(track.prev_sibling, model.TrackGroup))
            self.currentTrackChanged.emit(track)
        else:
            self._remove_button.setEnabled(False)
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)
            self.currentTrackChanged.emit(None)

    def onAddClicked(self, track_type):
        if self._model is None:
            return

        self.call_async(
            self._model.addTrack(
                track_type=track_type,
                parent_index=self._tracks_list.currentIndex()),
            callback=self.onAddTrackDone)

    def onAddTrackDone(self, added_index):
        self._tracks_list.setCurrentIndex(added_index)

    def onRemoveClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        self.call_async(self._model.removeTrack(index))

    def onMoveUpClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group
        assert not track.is_first

        self._model.send_command_async(
            track.id, 'MoveTrack',
            direction=-1,
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveDownClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group
        assert not track.is_last

        self._model.send_command_async(
            track.id, 'MoveTrack',
            direction=1,
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveLeftClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group

        new_parent = track.parent.parent

        self._model.send_command_async(
            track.id, 'ReparentTrack',
            new_parent=new_parent.id, index=track.parent.index + 1,
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveRightClicked(self):
        if self._model is None:
            return

        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group

        new_parent = track.prev_sibling
        assert isinstance(new_parent, model.TrackGroup)

        self._model.send_command_async(
            track.id, 'ReparentTrack',
            new_parent=new_parent.id, index=len(new_parent.tracks),
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveTrackDone(self, track):
        self._tracks_list.setCurrentIndex(
            self._model.indexForTrack(track))
