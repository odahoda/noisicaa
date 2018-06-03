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

import functools
import logging
import os.path
from typing import cast, Any, Optional, Iterator, List  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core  # pylint: disable=unused-import
from noisicaa.constants import DATA_DIR
from noisicaa import music
from noisicaa import model
from . import dock_widget
from . import ui_base

logger = logging.getLogger(__name__)


class TracksModelItem(object):
    def __init__(self, track: music.Track, parent: Optional['TracksModelItem']) -> None:
        self.track = track
        self.parent = parent
        self.children = []  # type: List[TracksModelItem]
        self.listeners = []  # type: List[core.Listener]

    def walk(self) -> Iterator['TracksModelItem']:
        yield self
        for child in self.children:
            yield from child.walk()


class TracksModel(ui_base.ProjectMixin, QtCore.QAbstractItemModel):
    VisibleRole = Qt.UserRole
    MuteRole = Qt.UserRole + 1

    COLUMNS = 2

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._root_item = self._buildItem(self.project.master_group, None)

        self._score_icon = QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-score.svg'))
        self._beat_icon = QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-beat.svg'))
        self._control_icon = QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-control.svg'))
        self._sample_icon = QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-sample.svg'))
        self._group_icon = QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-group.svg'))

    def _buildItem(
            self, track: music.Track, parent: Optional[TracksModelItem]) -> TracksModelItem:
        item = TracksModelItem(track, parent)

        if isinstance(track, music.TrackGroup):
            track = cast(music.TrackGroup, track)
            for child_track in track.tracks:
                item.children.append(self._buildItem(child_track, item))

            item.listeners.append(
                track.tracks_changed.add(functools.partial(self.onGroupChanged, item)))

        item.listeners.append(
            track.name_changed.add(functools.partial(self.onTrackChanged, item, 'name')))
        item.listeners.append(
            track.muted_changed.add(functools.partial(self.onTrackChanged, item, 'muted')))
        item.listeners.append(
            track.visible_changed.add(functools.partial(self.onTrackChanged, item, 'visible')))

        return item

    def close(self) -> None:
        for item in self._root_item.walk():
            for listener in item.listeners:
                listener.remove()
        self._root_item = None

    def onGroupChanged(self, group: TracksModelItem, change: model.PropertyListChange) -> None:
        group_index = self.indexForItem(group)
        if isinstance(change, model.PropertyListInsert):
            self.beginInsertRows(group_index, change.index, change.index)
            group.children.insert(change.index, self._buildItem(change.new_value, group))
            self.endInsertRows()
        elif isinstance(change, model.PropertyListDelete):
            self.beginRemoveRows(group_index, change.index, change.index)
            del group.children[change.index]
            self.endRemoveRows()
        else:
            raise TypeError(type(change))

    def onTrackChanged(
            self, item: TracksModelItem, prop: str, change: model.PropertyValueChange) -> None:
        track = item.track
        logger.info(
            "Value of %s on track %s: %s->%s", prop, track.id, change.old_value, change.new_value)
        self.dataChanged.emit(
            self.indexForItem(item, column=0),
            self.indexForItem(item, column=self.COLUMNS - 1),
            [])

    def track(self, index: QtCore.QModelIndex) -> music.Track:
        if not index.isValid():
            raise ValueError("Invalid index")

        item = index.internalPointer()
        assert item is not None
        return item.track

    def indexForTrack(self, track: music.Track) -> QtCore.QModelIndex:
        for item in self._root_item.walk():
            if item.track.id == track.id:
                return self.indexForItem(item)

        raise ValueError("Invalid track")

    def indexForItem(self, item: TracksModelItem, column: int = 0) -> QtCore.QModelIndex:
        if item.parent is None:
            return self.createIndex(0, column, item)
        else:
            return self.createIndex(item.parent.children.index(item), column, item)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.column() > 0:  # pragma: no coverage
            return 0

        if not parent.isValid():
            return 1

        parent_item = parent.internalPointer()
        if parent_item is None:
            return 0

        return len(parent_item.children)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return self.COLUMNS

    def index(
            self, row: int, column: int = 0, parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        if not parent.isValid():
            assert row == 0, row
            return self.createIndex(row, column, self._root_item)

        parent_item = parent.internalPointer()
        assert isinstance(parent_item.track, music.TrackGroup), parent_item.track

        item = parent_item.children[row]
        return self.createIndex(row, column, item)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:  # type: ignore
        if not index.isValid():
            return QtCore.QModelIndex()

        item = index.internalPointer()
        if item is None or item.parent is None:
            return QtCore.QModelIndex()

        return self.indexForItem(item.parent)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.column() == 0:
            flags |= Qt.ItemIsEditable
        return flags

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole) -> Any:
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
                if isinstance(track, music.ScoreTrack):
                    return self._score_icon
                elif isinstance(track, music.BeatTrack):
                    return self._beat_icon
                elif isinstance(track, music.ControlTrack):
                    return self._control_icon
                elif isinstance(track, music.SampleTrack):
                    return self._sample_icon
                elif isinstance(track, music.TrackGroup):
                    return self._group_icon
                else:
                    return None
        elif role == self.VisibleRole:
            return track.visible
        elif role == self.MuteRole:  # pragma: no branch
            return track.muted

        return None  # pragma: no coverage

    def setData(self, index: QtCore.QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False

        item = index.internalPointer()
        track = item.track

        if role == Qt.EditRole:
            self.send_command_async(music.Command(
                target=track.id,
                update_track_properties=music.UpdateTrackProperties(name=value)))
            return False
        elif role == self.VisibleRole:
            self.send_command_async(music.Command(
                target=track.id,
                update_track_properties=music.UpdateTrackProperties(visible=value)))
            return False
        elif role == self.MuteRole:
            self.send_command_async(music.Command(
                target=track.id,
                update_track_properties=music.UpdateTrackProperties(muted=value)))
            return False

        return False

    def headerData(
            self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:  # pragma: no coverage
        return None

    async def addTrack(
            self, track_type: str, parent_index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        if parent_index.isValid():
            parent_item = parent_index.internalPointer()
            if not isinstance(parent_item.track, music.TrackGroup):
                insert_index = parent_index.row() + 1
                parent_item = parent_item.parent
            else:
                insert_index = -1
        else:
            parent_item = self._root_item
            insert_index = -1

        parent_group = parent_item.track
        assert isinstance(parent_group, music.TrackGroup)

        list_index = await self.project_client.send_command(music.Command(
            target=self.project.id,
            add_track=music.AddTrack(
                parent_group_id=parent_group.id,
                insert_index=insert_index,
                track_type=track_type)))

        return self.index(list_index, 0, self.indexForItem(parent_item))

    async def removeTrack(self, index: QtCore.QModelIndex) -> None:
        track = index.internalPointer().track
        await self.project_client.send_command(music.Command(
            target=self.project.id,
            remove_track=music.RemoveTrack(track_id=track.id)))


class TrackItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._visible_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-visible.svg'))
        self._not_visible_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-visible.svg'))

        self._muted_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-muted.svg'))
        self._not_muted_icon = QtGui.QIcon(
            os.path.join(DATA_DIR, 'icons', 'track-not-muted.svg'))

    def sizeHint(
            self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex
    ) -> QtCore.QSize:
        size = super().sizeHint(option, index)
        if index.column() == 1:
            size = QtCore.QSize(2 * size.height() + 8, size.height())
        return size

    def showIconRect(self, rect: QtCore.QRect) -> QtCore.QRect:
        return QtCore.QRect(
            rect.x() + 4, rect.y() + 2,
            rect.height() - 4, rect.height() - 4)

    def playIconRect(self, rect: QtCore.QRect) -> QtCore.QRect:
        return QtCore.QRect(
            rect.x() + rect.height() + 6, rect.y() + 2,
            rect.height() - 4, rect.height() - 4)

    def itemRect(self, rect: QtCore.QRect) -> QtCore.QRect:
        return QtCore.QRect(
            rect.x() + 2 * rect.height() + 8, rect.y(),
            rect.width() - 2 * rect.height() + 8, rect.height())

    def paint(
            self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem,
            index: QtCore.QModelIndex) -> None:
        super().paint(painter, option, index)

        if index.column() == 1:
            track = index.internalPointer().track

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

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setHeaderHidden(True)
        self.setTreePosition(0)
        self.setExpandsOnDoubleClick(False)

        self._delegate = TrackItemDelegate()
        self.setItemDelegate(self._delegate)

    def setModel(self, tracks_model: QtCore.QAbstractItemModel) -> None:
        super().setModel(tracks_model)
        if tracks_model is not None:
            self.expandAll()
            self.header().resizeSection(1, self.sizeHintForColumn(1))
            self.header().swapSections(0, 1)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        index = self.indexAt(event.pos())
        if index.isValid() and index.column() == 1:
            rect = self.visualRect(index)
            tracks_model = self.model()
            if self._delegate.showIconRect(rect).contains(event.pos()):
                tracks_model.setData(
                    index, not tracks_model.data(index, TracksModel.VisibleRole),
                    TracksModel.VisibleRole)
                event.accept()
            elif self._delegate.playIconRect(rect).contains(event.pos()):
                tracks_model.setData(
                    index, not tracks_model.data(index, TracksModel.MuteRole),
                    TracksModel.MuteRole)
                event.accept()

        super().mousePressEvent(event)

    def currentChanged(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        self.currentIndexChanged.emit(current)


class TracksDockWidget(ui_base.ProjectMixin, dock_widget.DockWidget):
    currentTrackChanged = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            identifier='tracks',
            title="Tracks",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._add_score_track_action = QtWidgets.QAction("Score track", self)
        self._add_score_track_action.setIcon(
            QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-score.svg')))
        self._add_score_track_action.triggered.connect(
            functools.partial(self.onAddClicked, 'score'))

        self._add_beat_track_action = QtWidgets.QAction("Beat track", self)
        self._add_beat_track_action.setIcon(
            QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-beat.svg')))
        self._add_beat_track_action.triggered.connect(
            functools.partial(self.onAddClicked, 'beat'))

        self._add_control_track_action = QtWidgets.QAction("Control track", self)
        self._add_control_track_action.setIcon(
            QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-control.svg')))
        self._add_control_track_action.triggered.connect(
            functools.partial(self.onAddClicked, 'control'))

        self._add_sample_track_action = QtWidgets.QAction("Sample track", self)
        self._add_sample_track_action.setIcon(
            QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-sample.svg')))
        self._add_sample_track_action.triggered.connect(
            functools.partial(self.onAddClicked, 'sample'))

        self._add_track_group_action = QtWidgets.QAction("Group", self)
        self._add_track_group_action.setIcon(
            QtGui.QIcon(os.path.join(DATA_DIR, 'icons', 'track-type-group.svg')))
        self._add_track_group_action.triggered.connect(
            functools.partial(self.onAddClicked, 'group'))

        self._add_track_menu = QtWidgets.QMenu()
        self._add_track_menu.addAction(self._add_score_track_action)
        self._add_track_menu.addAction(self._add_beat_track_action)
        self._add_track_menu.addAction(self._add_control_track_action)
        self._add_track_menu.addAction(self._add_sample_track_action)
        self._add_track_menu.addAction(self._add_track_group_action)

        self._add_button = QtWidgets.QToolButton()
        self._add_button.setIcon(QtGui.QIcon.fromTheme('list-add'))
        self._add_button.setIconSize(QtCore.QSize(16, 16))
        self._add_button.setAutoRaise(True)
        self._add_button.setMenu(self._add_track_menu)
        self._add_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self._remove_button = QtWidgets.QToolButton()
        self._remove_button.setIcon(QtGui.QIcon.fromTheme('list-remove'))
        self._remove_button.setIconSize(QtCore.QSize(16, 16))
        self._remove_button.setAutoRaise(True)
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(self.onRemoveClicked)

        self._move_up_button = QtWidgets.QToolButton()
        self._move_up_button.setIcon(QtGui.QIcon.fromTheme('go-up'))
        self._move_up_button.setIconSize(QtCore.QSize(16, 16))
        self._move_up_button.setAutoRaise(True)
        self._move_up_button.setEnabled(False)
        self._move_up_button.clicked.connect(self.onMoveUpClicked)

        self._move_down_button = QtWidgets.QToolButton()
        self._move_down_button.setIcon(QtGui.QIcon.fromTheme('go-down'))
        self._move_down_button.setIconSize(QtCore.QSize(16, 16))
        self._move_down_button.setAutoRaise(True)
        self._move_down_button.setEnabled(False)
        self._move_down_button.clicked.connect(self.onMoveDownClicked)

        self._move_left_button = QtWidgets.QToolButton()
        self._move_left_button.setIcon(QtGui.QIcon.fromTheme('go-previous'))
        self._move_left_button.setIconSize(QtCore.QSize(16, 16))
        self._move_left_button.setAutoRaise(True)
        self._move_left_button.setEnabled(False)
        self._move_left_button.clicked.connect(self.onMoveLeftClicked)

        self._move_right_button = QtWidgets.QToolButton()
        self._move_right_button.setIcon(QtGui.QIcon.fromTheme('go-next'))
        self._move_right_button.setIconSize(QtCore.QSize(16, 16))
        self._move_right_button.setAutoRaise(True)
        self._move_right_button.setEnabled(False)
        self._move_right_button.clicked.connect(self.onMoveRightClicked)

        self._tracks_list = TrackList(self)
        self._tracks_list.currentIndexChanged.connect(self.onCurrentChanged)

        self._model = TracksModel(context=self.context)
        self._tracks_list.setModel(self._model)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setSpacing(1)
        buttons_layout.addWidget(self._add_button)
        buttons_layout.addWidget(self._remove_button)
        buttons_layout.addWidget(self._move_up_button)
        buttons_layout.addWidget(self._move_down_button)
        buttons_layout.addWidget(self._move_left_button)
        buttons_layout.addWidget(self._move_right_button)
        buttons_layout.addStretch(1)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(1)
        main_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        main_layout.addWidget(self._tracks_list, 1)
        main_layout.addLayout(buttons_layout)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(main_layout)
        self.setWidget(main_area)

    def onCurrentChanged(
            self, index: QtCore.QModelIndex, previous: QtCore.QModelIndex = None) -> None:
        if index is not None and index.isValid():
            track = self._model.track(index)
            self._remove_button.setEnabled(not track.is_master_group)
            self._move_up_button.setEnabled(
                not track.is_master_group and not track.is_first)
            self._move_down_button.setEnabled(
                not track.is_master_group and not track.is_last)
            self._move_left_button.setEnabled(
                not track.is_master_group and not cast(music.Track, track.parent).is_master_group)
            self._move_right_button.setEnabled(
                not track.is_master_group and not track.is_first
                and isinstance(track.prev_sibling, music.TrackGroup))
            self.currentTrackChanged.emit(track)
        else:
            self._remove_button.setEnabled(False)
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)
            self._move_left_button.setEnabled(False)
            self._move_right_button.setEnabled(False)
            self.currentTrackChanged.emit(None)

    def onAddClicked(self, track_type: str) -> None:
        self.call_async(
            self._model.addTrack(
                track_type=track_type,
                parent_index=self._tracks_list.currentIndex()),
            callback=self.onAddTrackDone)

    def onAddTrackDone(self, added_index: QtCore.QModelIndex) -> None:
        self._tracks_list.setCurrentIndex(added_index)

    def onRemoveClicked(self) -> None:
        index = self._tracks_list.currentIndex()
        self.call_async(self._model.removeTrack(index))

    def onMoveUpClicked(self) -> None:
        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group
        assert not track.is_first

        self._model.send_command_async(
            music.Command(
                target=track.id,
                move_track=music.MoveTrack(direction=-1)),
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveDownClicked(self) -> None:
        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group
        assert not track.is_last

        self._model.send_command_async(
            music.Command(
                target=track.id,
                move_track=music.MoveTrack(direction=1)),
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveLeftClicked(self) -> None:
        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group

        new_parent = track.parent.parent

        self._model.send_command_async(
            music.Command(
                target=track.id,
                reparent_track=music.ReparentTrack(
                    new_parent=new_parent.id, index=track.parent.index + 1)),
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveRightClicked(self) -> None:
        index = self._tracks_list.currentIndex()
        assert index.isValid()
        track = self._model.track(index)
        assert not track.is_master_group

        new_parent = track.prev_sibling
        assert isinstance(new_parent, music.TrackGroup)

        self._model.send_command_async(
            music.Command(
                target=track.id,
                reparent_track=music.ReparentTrack(
                    new_parent=new_parent.id, index=len(new_parent.tracks))),
            callback=lambda _: self.onMoveTrackDone(track))

        self._tracks_list.setCurrentIndex(QtCore.QModelIndex())

    def onMoveTrackDone(self, track: music.Track) -> None:
        self._tracks_list.setCurrentIndex(self._model.indexForTrack(track))
