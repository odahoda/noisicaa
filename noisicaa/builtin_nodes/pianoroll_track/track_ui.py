#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import fractions
import functools
import logging
import os.path
from typing import Any, Dict, List, Set, Sequence, Tuple

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import constants
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import clipboard
from noisicaa.ui import pianoroll
from noisicaa.ui import slots
from noisicaa.ui import int_dial
from noisicaa.ui.track_list import tools
from noisicaa.ui.track_list import base_track_editor
from noisicaa.ui.track_list import time_view_mixin
from noisicaa.builtin_nodes.pianoroll import processor_messages
from . import model
from . import clipboard_pb2

logger = logging.getLogger(__name__)


class PianoRollToolMixin(tools.ToolBase):  # pylint: disable=abstract-method
    track = None  # type: PianoRollTrackEditor

    def activateSegment(self, segment: 'SegmentEditor') -> None:
        pass

    def activated(self) -> None:
        for segment in self.track.segments:
            self.activateSegment(segment)
        super().activated()

    def __changeRowHeight(
            self,
            delta: int,
            label: QtWidgets.QLabel,
            increase_button: QtWidgets.QToolButton,
            decrease_button: QtWidgets.QToolButton
    ) -> None:
        tr = self.track
        pos = (tr.yOffset() + tr.height() / 2) / tr.gridHeight()
        tr.setGridYSize(
            max(tr.MIN_GRID_Y_SIZE, min(tr.MAX_GRID_Y_SIZE, tr.gridYSize() + delta)))
        tr.setYOffset(
            max(0, min(tr.gridHeight() - tr.height(),
                       int(pos * tr.gridHeight() - tr.height() / 2))))
        label.setText("%dpx" % tr.gridYSize())
        increase_button.setEnabled(tr.gridYSize() < tr.MAX_GRID_Y_SIZE)
        decrease_button.setEnabled(tr.gridYSize() > tr.MIN_GRID_Y_SIZE)

    def buildContextMenu(self, menu: QtWidgets.QMenu, evt: QtGui.QContextMenuEvent) -> None:
        view_menu = menu.addMenu("View")

        increase_row_height_button = QtWidgets.QToolButton()
        increase_row_height_button.setObjectName('incr-row-height')
        increase_row_height_button.setAutoRaise(True)
        increase_row_height_button.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'zoom-in.svg')))
        increase_row_height_button.setEnabled(self.track.gridYSize() < self.track.MAX_GRID_Y_SIZE)
        decrease_row_height_button = QtWidgets.QToolButton()
        decrease_row_height_button.setObjectName('decr-row-height')
        decrease_row_height_button.setAutoRaise(True)
        decrease_row_height_button.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'zoom-out.svg')))
        decrease_row_height_button.setEnabled(self.track.gridYSize() > self.track.MIN_GRID_Y_SIZE)

        row_height_label = QtWidgets.QLabel("%dpx" % self.track.gridYSize())

        increase_row_height_button.clicked.connect(functools.partial(
            self.__changeRowHeight,
            1, row_height_label, increase_row_height_button, decrease_row_height_button))
        decrease_row_height_button.clicked.connect(functools.partial(
            self.__changeRowHeight,
            -1, row_height_label, increase_row_height_button, decrease_row_height_button))

        row_height_widget = QtWidgets.QWidget()
        l = QtWidgets.QHBoxLayout()
        l.setContentsMargins(10, 2, 10, 2)
        l.setSpacing(4)
        l.addWidget(QtWidgets.QLabel("Row height:"))
        l.addWidget(decrease_row_height_button)
        l.addWidget(row_height_label)
        l.addWidget(increase_row_height_button)
        l.addStretch(1)
        row_height_widget.setLayout(l)

        row_height_action = QtWidgets.QWidgetAction(self)
        row_height_action.setDefaultWidget(row_height_widget)
        view_menu.addAction(row_height_action)

        current_channel_menu = menu.addMenu("Current MIDI Channel")
        for ch in range(16):
            current_channel_menu.addAction(
                self.track.set_current_channel_actions[ch])


    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu(self.track)
        menu.setObjectName('context-menu')
        self.buildContextMenu(menu, evt)
        menu.popup(evt.globalPos())
        evt.accept()


class ArrangeSegmentsTool(PianoRollToolMixin, tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.PIANOROLL_ARRANGE_SEGMENTS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

        self.__action = None  # type: str

        self.__resize_segment = None  # type: SegmentEditor
        self.__drag_segments = None  # type: List[SegmentEditor]
        self.__handle_offset = None  # type: int
        self.__ref_time = None  # type: audioproc.MusicalTime
        self.__time = None  # type: audioproc.MusicalTime

        self.__select_all_action = QtWidgets.QAction(self)
        self.__select_all_action.setObjectName('select-all')
        self.__select_all_action.setText("Select All")
        self.__select_all_action.setShortcut('ctrl+a')
        self.__select_all_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__select_all_action.triggered.connect(self.__selectAll)

        self.__clear_selection_action = QtWidgets.QAction(self)
        self.__clear_selection_action.setObjectName('clear-selection')
        self.__clear_selection_action.setText("Clear Selection")
        self.__clear_selection_action.setShortcut('ctrl+shift+a')
        self.__clear_selection_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__clear_selection_action.triggered.connect(self.__clearSelection)

        self.__add_segment_action = QtWidgets.QAction(self)
        self.__add_segment_action.setObjectName('add-segment')
        self.__add_segment_action.setText("Add Segment")
        self.__add_segment_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'list-add.svg')))
        self.__add_segment_action.setShortcut('ins')
        self.__add_segment_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__add_segment_action.triggered.connect(self.__createSegment)

        self.__delete_segment_action = QtWidgets.QAction(self)
        self.__delete_segment_action.setObjectName('delete-segment')
        self.__delete_segment_action.setText("Delete Segment(s)")
        self.__delete_segment_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'list-remove.svg')))
        self.__delete_segment_action.setShortcut('del')
        self.__delete_segment_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.__delete_segment_action.triggered.connect(self.__deleteSegments)

    def iconName(self) -> str:
        return 'pianoroll-arrange-segments'

    def keySequence(self) -> QtGui.QKeySequence:
        return QtGui.QKeySequence('a')

    def activateSegment(self, segment: 'SegmentEditor') -> None:
        segment.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        segment.setReadOnly(True)

    def activated(self) -> None:
        self.track.addAction(self.__select_all_action)
        self.track.addAction(self.__clear_selection_action)
        self.track.addAction(self.__add_segment_action)
        self.track.addAction(self.__delete_segment_action)
        super().activated()

    def deactivated(self) -> None:
        self.track.removeAction(self.__select_all_action)
        self.track.removeAction(self.__clear_selection_action)
        self.track.removeAction(self.__add_segment_action)
        self.track.removeAction(self.__delete_segment_action)
        self.track.setInsertTime(audioproc.MusicalTime(-1, 1))
        self.track.clearSelection()
        self.track.unsetCursor()
        super().deactivated()

    def __selectAll(self) -> None:
        for segment in self.track.segments:
            self.track.addToSelection(segment)

    def __clearSelection(self) -> None:
        self.track.clearSelection()

    def __createSegment(self) -> None:
        time = self.track.insertTime()
        if time < audioproc.MusicalTime(0, 1):
            time = audioproc.MusicalTime(0, 1)

        tr = self.track
        with tr.project.apply_mutations('%s: Add segment' % tr.track.name):
            tr.track.create_segment(
                time, audioproc.MusicalDuration(16, 4))

    def __deleteSegments(self) -> None:
        segments = self.track.selection()
        tr = self.track
        with tr.project.apply_mutations('%s: Remove segment(s)' % tr.track.name):
            for segment in segments:
                tr.track.remove_segment(segment.segmentRef())

    def __splitSegment(self, segment: 'SegmentEditor', split_time: audioproc.MusicalTime) -> None:
        assert segment.startTime() < split_time < segment.endTime()

        tr = self.track
        with tr.project.apply_mutations('%s: Split segment' % tr.track.name):
            tr.track.split_segment(segment.segmentRef(), split_time)

    def buildContextMenu(self, menu: QtWidgets.QMenu, evt: QtGui.QContextMenuEvent) -> None:
        super().buildContextMenu(menu, evt)

        menu.addSeparator()

        menu.addAction(self.app.clipboard.cut_action)
        menu.addAction(self.app.clipboard.copy_action)
        menu.addAction(self.app.clipboard.paste_action)
        menu.addAction(self.app.clipboard.paste_as_link_action)

        menu.addSeparator()

        menu.addAction(self.__select_all_action)
        menu.addAction(self.__clear_selection_action)

        menu.addSeparator()

        menu.addAction(self.__add_segment_action)
        menu.addAction(self.__delete_segment_action)

        playback_position = self.track.playbackPosition()
        split_segment = self.track.segmentAtTime(playback_position)
        if (split_segment is not None
                and not split_segment.startTime() < playback_position < split_segment.endTime()):
            split_segment = None
        split_segment_action = QtWidgets.QAction(menu)
        split_segment_action.setObjectName('split-segment')
        split_segment_action.setText("Split Segment")
        split_segment_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'pianoroll-split-segment.svg')))
        if split_segment is not None:
            split_segment_action.triggered.connect(
                functools.partial(self.__splitSegment, split_segment, playback_position))
        else:
            split_segment_action.setEnabled(False)
        menu.addAction(split_segment_action)

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        if self.__action is not None:
            evt.accept()
            return

        if self.track.insertTime() < audioproc.MusicalTime(0, 1):
            self.track.setInsertTime(self.track.xToTime(evt.pos().x()))

        segment = self.track.segmentAt(evt.pos().x())
        if segment is not None and not segment.selected():
            self.track.clearSelection()
            self.track.addToSelection(segment)

        super().contextMenuEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            click_segment = self.track.segmentAt(evt.pos().x())
            if click_segment is not None:
                if evt.modifiers() == Qt.NoModifier and not click_segment.selected():
                    self.track.clearSelection()
                    self.track.addToSelection(click_segment)
                elif evt.modifiers() == Qt.ControlModifier:
                    if click_segment.selected():
                        self.track.removeFromSelection(click_segment)
                    else:
                        self.track.addToSelection(click_segment)
                elif evt.modifiers() == Qt.ShiftModifier and self.track.lastSelected() is not None:
                    start_time = min(
                        click_segment.startTime(), self.track.lastSelected().startTime())
                    end_time = max(click_segment.endTime(), self.track.lastSelected().endTime())
                    for segment in self.track.segments:
                        if segment.startTime() >= start_time and segment.endTime() <= end_time:
                            self.track.addToSelection(segment)

            elif evt.modifiers() == Qt.NoModifier:
                self.track.clearSelection()

        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            for seditor in reversed(self.track.segments):
                x1 = self.track.timeToX(seditor.startTime())
                x2 = self.track.timeToX(seditor.endTime())

                if abs(x2 - evt.pos().x()) < 4:
                    self.track.setInsertTime(audioproc.MusicalTime(-1, 1))
                    self.track.clearSelection()
                    self.track.addToSelection(seditor)
                    self.__action = 'move-end'
                    self.__resize_segment = seditor
                    self.__handle_offset = evt.pos().x() - x2
                    self.__time = seditor.endTime()
                    evt.accept()
                    return

                if abs(x1 - evt.pos().x()) < 4:
                    self.track.setInsertTime(audioproc.MusicalTime(-1, 1))
                    self.track.clearSelection()
                    self.track.addToSelection(seditor)
                    self.__action = 'move-start'
                    self.__resize_segment = seditor
                    self.__handle_offset = evt.pos().x() - x1
                    self.__time = seditor.startTime()
                    evt.accept()
                    return

                if x1 <= evt.pos().x() < x2:
                    self.track.setInsertTime(audioproc.MusicalTime(-1, 1))
                    self.__action = 'drag'
                    if seditor.selected():
                        self.__drag_segments = self.track.selection()
                    else:
                        self.__drag_segments = [seditor]
                    self.__ref_time = min(s.startTime() for s in self.__drag_segments)
                    self.__handle_offset = evt.pos().x() - self.track.timeToX(self.__ref_time)
                    self.__time = self.__ref_time
                    evt.accept()
                    return

            self.track.setInsertTime(self.track.xToTime(evt.pos().x()))
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__action == 'drag':
            self.__time = self.track.xToTime(evt.pos().x() - self.__handle_offset)
            if self.track.shouldSnap(evt):
                self.__time = self.track.snapTime(self.__time)
            self.__time = max(audioproc.MusicalTime(0, 1), self.__time)
            for segment in self.__drag_segments:
                segment.setShowPlaybackPosition(False)
                time = self.__time + (segment.startTime() - self.__ref_time)
                self.track.repositionSegment(
                    segment, time, time + segment.duration())
            evt.accept()
            return

        if self.__action == 'move-end':
            self.__resize_segment.setShowPlaybackPosition(False)
            self.__time = self.track.xToTime(evt.pos().x() - self.__handle_offset)
            if self.track.shouldSnap(evt):
                self.__time = self.track.snapTime(self.__time)
            self.__time = max(
                self.__resize_segment.startTime() + audioproc.MusicalDuration(1, 16),
                self.__time)
            self.track.repositionSegment(
                self.__resize_segment, self.__resize_segment.startTime(), self.__time)
            self.__resize_segment.setDuration(self.__time - self.__resize_segment.startTime())
            evt.accept()
            return

        if self.__action == 'move-start':
            self.__resize_segment.setShowPlaybackPosition(False)
            self.__time = self.track.xToTime(evt.pos().x() - self.__handle_offset)
            if self.track.shouldSnap(evt):
                self.__time = self.track.snapTime(self.__time)
            self.__time = min(
                self.__resize_segment.endTime() - audioproc.MusicalDuration(1, 16),
                self.__time)
            self.track.repositionSegment(
                self.__resize_segment, self.__time, self.__resize_segment.endTime())
            self.__resize_segment.setDuration(self.__resize_segment.endTime() - self.__time)
            evt.accept()
            return

        for seditor in reversed(self.track.segments):
            x1 = self.track.timeToX(seditor.startTime())
            x2 = self.track.timeToX(seditor.endTime())

            if abs(x2 - evt.pos().x()) < 4:
                self.track.setCursor(Qt.SizeHorCursor)
                break
            elif abs(x1 - evt.pos().x()) < 4:
                self.track.setCursor(Qt.SizeHorCursor)
                break
            elif x1 <= evt.pos().x() < x2:
                self.track.setCursor(Qt.DragMoveCursor)
                break
        else:
            self.track.unsetCursor()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__action == 'drag':
            with self.project.apply_mutations('%s: Move segment' % self.track.track.name):
                for segment in self.__drag_segments:
                    segment.setShowPlaybackPosition(True)
                    segment.segmentRef().time += self.__time - self.__ref_time
            self.track.updatePlaybackPosition()
            self.__drag_segments.clear()
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.LeftButton and self.__action == 'move-start':
            self.__resize_segment.setShowPlaybackPosition(True)
            with self.project.apply_mutations('%s: Resize segment' % self.track.track.name):
                delta_time = self.__time - self.__resize_segment.startTime()
                self.__resize_segment.segmentRef().time = self.__time
                self.__resize_segment.segment().duration -= delta_time
            self.track.updatePlaybackPosition()
            self.__resize_segment = None
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.LeftButton and self.__action == 'move-end':
            self.__resize_segment.setShowPlaybackPosition(True)
            with self.project.apply_mutations('%s: Resize segment' % self.track.track.name):
                delta_time = self.__time - self.__resize_segment.endTime()
                self.__resize_segment.segment().duration += delta_time
            self.track.updatePlaybackPosition()
            self.__resize_segment = None
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__action == 'drag':
            for segment in self.__drag_segments:
                segment.setShowPlaybackPosition(True)
                self.track.repositionSegment(segment, segment.startTime(), segment.endTime())
            self.track.updatePlaybackPosition()
            self.__resize_segment = None
            self.__action = None
            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__action in ('move-start', 'move-end'):
            self.__resize_segment.setShowPlaybackPosition(True)
            self.track.repositionSegment(
                self.__resize_segment,
                self.__resize_segment.startTime(), self.__resize_segment.endTime())
            self.__resize_segment.setDuration(self.__resize_segment.duration())
            self.track.updatePlaybackPosition()
            self.__resize_segment = None
            self.__action = None
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            seditor = self.track.segmentAt(evt.pos().x())
            if seditor is not None:
                self.track.setCurrentToolType(tools.ToolType.PIANOROLL_EDIT_EVENTS)
                seditor.activate()

            evt.accept()
            return

        super().mouseDoubleClickEvent(evt)


class EditEventsTool(PianoRollToolMixin, tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.PIANOROLL_EDIT_EVENTS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

    def iconName(self) -> str:
        return 'pianoroll-edit-events'

    def keySequence(self) -> QtGui.QKeySequence:
        return QtGui.QKeySequence('e')

    def activateSegment(self, segment: 'SegmentEditor') -> None:
        segment.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        segment.setReadOnly(False)
        segment.setEditMode(pianoroll.EditMode.AddInterval)

    def activated(self) -> None:
        self.track.setShowVelocity(True)
        super().activated()

    def deactivated(self) -> None:
        self.track.setShowVelocity(False)
        super().deactivated()


class SelectEventsTool(PianoRollToolMixin, tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.PIANOROLL_SELECT_EVENTS,
            group=tools.ToolGroup.EDIT,
            **kwargs)

    def iconName(self) -> str:
        return 'pianoroll-select-events'

    def keySequence(self) -> QtGui.QKeySequence:
        return QtGui.QKeySequence('s')

    def activateSegment(self, segment: 'SegmentEditor') -> None:
        segment.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        segment.setReadOnly(False)
        segment.setEditMode(pianoroll.EditMode.SelectRect)


class EditVelocityTool(PianoRollToolMixin, tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.PIANOROLL_EDIT_VELOCITY,
            group=tools.ToolGroup.EDIT,
            **kwargs)

    def iconName(self) -> str:
        return 'pianoroll-edit-velocity'

    def keySequence(self) -> QtGui.QKeySequence:
        return QtGui.QKeySequence('v')

    def activateSegment(self, segment: 'SegmentEditor') -> None:
        segment.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        segment.setReadOnly(False)
        segment.setEditMode(pianoroll.EditMode.EditVelocity)


class SegmentEditor(
        slots.SlotContainer, core.AutoCleanupMixin, ui_base.ProjectMixin, QtWidgets.QWidget):
    playNotes = QtCore.pyqtSignal(pianoroll.PlayNotes)

    xOffset, setXOffset, xOffsetChanged = slots.slot(int, 'xOffset', default=0)
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    scaleX, setScaleX, scaleXChanged = slots.slot(
        fractions.Fraction, 'scaleX', default=fractions.Fraction(4*80))
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)
    readOnly, setReadOnly, readOnlyChanged = slots.slot(bool, 'readOnly', default=True)
    editMode, setEditMode, editModeChanged = slots.slot(
        pianoroll.EditMode, 'editMode', default=pianoroll.EditMode.AddInterval)
    currentChannel, setCurrentChannel, currentChannelChanged = slots.slot(
        int, 'currentChannel', default=0)
    playbackPosition, setPlaybackPosition, playbackPositionChanged = slots.slot(
        audioproc.MusicalTime, 'playbackPosition', default=audioproc.MusicalTime(-1, 1))
    insertVelocity, setInsertVelocity, insertVelocityChanged = slots.slot(
        int, 'insertVelocity', default=100)
    selected, setSelected, selectedChanged = slots.slot(bool, 'selected', default=False)
    showPlaybackPosition, setShowPlaybackPosition, showPlaybackPositionChanged = slots.slot(
        bool, 'showPlaybackPosition', default=True)

    def __init__(
            self, *,
            track_editor: 'PianoRollTrackEditor',
            segment_ref: model.PianoRollSegmentRef,
            **kwargs: Any
    ) -> None:
        super().__init__(parent=track_editor, **kwargs)

        self.setObjectName('segment-editor[%016x]' % segment_ref.id)

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__track_editor = track_editor
        self.__segment_ref = segment_ref
        self.__segment = segment_ref.segment

        self.__listeners.add(self.__segment_ref.time_changed.add(self.__timeChanged))
        self.__listeners.add(self.__segment.duration_changed.add(self.__durationChanged))

        self.__grid = pianoroll.PianoRollGrid(parent=self)
        self.__grid.setObjectName('grid')
        self.__grid.move(0, 0)
        self.__grid.setDuration(self.__segment.duration)
        self.__grid.setXOffset(self.xOffset())
        self.xOffsetChanged.connect(self.__grid.setXOffset)
        self.__grid.setYOffset(self.yOffset())
        self.yOffsetChanged.connect(self.__grid.setYOffset)
        self.__grid.setGridXSize(self.scaleX())
        self.scaleXChanged.connect(self.__grid.setGridXSize)
        self.__grid.setReadOnly(self.readOnly())
        self.readOnlyChanged.connect(self.__grid.setReadOnly)
        self.__grid.setEditMode(self.editMode())
        self.editModeChanged.connect(self.__grid.setEditMode)
        self.__grid.setCurrentChannel(self.currentChannel())
        self.currentChannelChanged.connect(self.__grid.setCurrentChannel)
        self.__grid.setInsertVelocity(self.insertVelocity())
        self.insertVelocityChanged.connect(self.__grid.setInsertVelocity)
        self.__grid.hoverPitchChanged.connect(self.__track_editor.setHoverPitch)
        self.__grid.playNotes.connect(self.playNotes.emit)
        self.__listeners.add(self.__grid.mutations.add(self.__gridMutations))

        self.selectedChanged.connect(self.__selectedChanged)
        self.playbackPositionChanged.connect(lambda _: self.__updatePlaybackPosition())
        self.showPlaybackPositionChanged.connect(lambda _: self.__updatePlaybackPosition())

        self.__ignore_model_mutations = False
        self.__obj_to_grid_map = {}  # type: Dict[int, int]
        self.__grid_to_obj_map = {}  # type: Dict[int, int]
        for event in self.__segment.events:
            event_id = self.__grid.addEvent(event.midi_event)
            self.__grid_to_obj_map[event_id] = event
            self.__obj_to_grid_map[event.id] = event_id
        self.__listeners.add(self.__segment.events_changed.add(self.__eventsChanged))

        self.gridYSizeChanged.connect(self.__gridYSizeChanged)

    def __selectedChanged(self, selected: bool) -> None:
        if selected:
            self.__grid.setOverlayColor(QtGui.QColor(150, 150, 255, 150))
        else:
            self.__grid.setOverlayColor(QtGui.QColor(0, 0, 0, 0))

    def __updatePlaybackPosition(self) -> None:
        if self.showPlaybackPosition():
            self.__grid.setPlaybackPosition(self.playbackPosition())
        else:
            self.__grid.setPlaybackPosition(audioproc.MusicalTime(-1, 1))

    def __timeChanged(self, change: music.PropertyValueChange[audioproc.MusicalTime]) -> None:
        self.__track_editor.repositionSegment(
            self, change.new_value, change.new_value + self.__segment.duration)

    def __durationChanged(
            self, change: music.PropertyValueChange[audioproc.MusicalDuration]) -> None:
        self.__track_editor.repositionSegment(
            self, self.__segment_ref.time, self.__segment_ref.time + change.new_value)
        self.__grid.setDuration(change.new_value)

    def __eventsChanged(self, change: music.PropertyListChange[model.PianoRollEvent]) -> None:
        if self.__ignore_model_mutations:
            return

        if isinstance(change, music.PropertyListInsert):
            event = change.new_value
            grid_id = self.__grid.addEvent(event.midi_event)
            self.__grid_to_obj_map[grid_id] = event
            self.__obj_to_grid_map[event.id] = grid_id

        elif isinstance(change, music.PropertyListDelete):
            event = change.old_value
            grid_id = self.__obj_to_grid_map[event.id]
            self.__grid.removeEvent(grid_id)
            del self.__grid_to_obj_map[grid_id]
            del self.__obj_to_grid_map[event.id]

        else:
            raise ValueError(type(change))

    def __gridMutations(self, mutations: Sequence[pianoroll.Mutation]) -> None:
        self.__ignore_model_mutations = True
        try:
            with self.project.apply_mutations(
                    '%s: Edit MIDI events' % self.__track_editor.track.name):
                for mutation in mutations:
                    if isinstance(mutation, pianoroll.AddEvent):
                        event = self.__segment.add_event(mutation.event)
                        self.__grid_to_obj_map[mutation.event_id] = event
                        self.__obj_to_grid_map[event.id] = mutation.event_id

                    elif isinstance(mutation, pianoroll.RemoveEvent):
                        event = self.__grid_to_obj_map[mutation.event_id]
                        self.__segment.remove_event(event)
                        del self.__grid_to_obj_map[mutation.event_id]
                        del self.__obj_to_grid_map[event.id]

                    else:
                        raise ValueError(type(mutation))
        finally:
            self.__ignore_model_mutations = False

    def __gridYSizeChanged(self, size: int) -> None:
        self.__grid.setGridYSize(size)

    def segmentRef(self) -> model.PianoRollSegmentRef:
        return self.__segment_ref

    def segment(self) -> model.PianoRollSegment:
        return self.__segment

    def startTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time

    def endTime(self) -> audioproc.MusicalTime:
        return self.__segment_ref.time + self.__segment.duration

    def duration(self) -> audioproc.MusicalDuration:
        return self.__segment.duration

    def setDuration(self, duration: audioproc.MusicalDuration) -> None:
        self.__grid.setDuration(duration)

    def activate(self) -> None:
        self.__grid.setFocus()

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        self.__grid.resize(self.width(), self.height())
        super().resizeEvent(evt)


class InsertCursor(QtWidgets.QWidget):
    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.fillRect(0, 0, 1, self.height(), QtGui.QColor(160, 160, 255))
        painter.fillRect(1, 0, 1, self.height(), QtGui.QColor(0, 0, 255))
        painter.fillRect(2, 0, 1, self.height(), QtGui.QColor(160, 160, 255))


class PianoRollTrackEditor(
        clipboard.CopyableMixin,
        time_view_mixin.ContinuousTimeMixin,
        base_track_editor.BaseTrackEditor):
    yOffset, setYOffset, yOffsetChanged = slots.slot(int, 'yOffset', default=0)
    gridYSize, setGridYSize, gridYSizeChanged = slots.slot(int, 'gridYSize', default=15)
    hoverPitch, setHoverPitch, hoverPitchChanged = slots.slot(int, 'hoverPitch', default=-1)
    snapToGrid, setSnapToGrid, snapToGridChanged = slots.slot(bool, 'snapToGrid', default=True)
    currentChannel, setCurrentChannel, currentChannelChanged = slots.slot(
        int, 'currentChannel', default=0)
    showVelocity, setShowVelocity, showVelocityChanged = slots.slot(
        bool, 'showVelocity', default=False)
    insertTime, setInsertTime, insertTimeChanged = slots.slot(
        audioproc.MusicalTime, 'insertTime', default=audioproc.MusicalTime(-1, 1))

    MIN_GRID_Y_SIZE = 2
    MAX_GRID_Y_SIZE = 64

    def __init__(self, **kwargs: Any) -> None:
        self.segments = []  # type: List[SegmentEditor]
        self.__segment_map = {}  # type: Dict[int, SegmentEditor]
        self.__selection = set()  # type: Set[int]
        self.__last_selected = None  # type: SegmentEditor

        super().__init__(**kwargs)

        self.__session_prefix = 'pianoroll-track:%016x:' % self.track.id
        self.__first_show = True

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__active_notes = set()  # type: Set[Tuple[int, int]]
        self.__hover_pitch = -1

        self.__keys = pianoroll.PianoKeys(parent=self)
        self.__keys.setPlayable(True)
        self.__keys.setPlaybackChannel(self.currentChannel())
        self.currentChannelChanged.connect(self.__keys.setPlaybackChannel)
        self.__keys.playNotes.connect(self.playNotes)
        self.__keys.setScrollable(True)
        self.__keys.setYOffset(self.yOffset())
        self.__keys.yOffsetChanged.connect(self.setYOffset)
        self.yOffsetChanged.connect(self.__keys.setYOffset)
        self.__keys.setGridYSize(self.gridYSize())
        self.gridYSizeChanged.connect(self.__keys.setGridYSize)
        self.hoverPitchChanged.connect(self.__hoverPitchChanged)

        self.__y_scrollbar = QtWidgets.QScrollBar(orientation=Qt.Vertical, parent=self)
        self.__y_scrollbar.setFixedWidth(16)
        self.__y_scrollbar.setRange(0, 500)
        self.__y_scrollbar.setSingleStep(20)
        self.__y_scrollbar.setPageStep(self.height())
        self.__y_scrollbar.setValue(self.yOffset())
        self.yOffsetChanged.connect(self.__y_scrollbar.setValue)
        self.__y_scrollbar.valueChanged.connect(self.setYOffset)

        self.__velocity = int_dial.IntDial(self)
        self.__velocity.setFixedSize(48, 48)
        self.__velocity.setValue(
            self.get_session_value(self.__session_prefix + 'new-interval-velocity', 100))
        self.__velocity.valueChanged.connect(functools.partial(
            self.set_session_value, self.__session_prefix + 'new-interval-velocity'))
        self.__velocity.setRange(1, 127)

        label = QtWidgets.QLabel("Velocity")
        font = QtGui.QFont(label.font())
        font.setPointSizeF(font.pointSizeF() / 1.2)
        label.setFont(font)

        l = QtWidgets.QVBoxLayout()
        l.setContentsMargins(2, 0, 0, 0)
        l.setSpacing(0)
        l.addWidget(self.__velocity, 0, Qt.AlignHCenter)
        l.addWidget(label, 0, Qt.AlignHCenter)

        self.__velocity_group = QtWidgets.QWidget(self)
        self.__velocity_group.setLayout(l)
        self.__velocity_group.setVisible(self.showVelocity())
        self.showVelocityChanged.connect(self.__velocity_group.setVisible)

        self.__insert_cursor = InsertCursor(self)
        self.updateInsertTime()

        for segment_ref in self.track.segments:
            self.__addSegment(len(self.segments), segment_ref)
        self.__listeners.add(self.track.segments_changed.add(self.__segmentsChanged))

        self.setAutoScroll(False)
        self.setFixedHeight(240)

        self.xOffsetChanged.connect(lambda _: self.__repositionSegments())
        self.xOffsetChanged.connect(lambda _: self.update())
        self.scaleXChanged.connect(lambda _: self.__repositionSegments())
        self.gridYSizeChanged.connect(lambda _: self.__updateYScrollbar())
        self.playbackPositionChanged.connect(lambda _: self.updatePlaybackPosition())
        self.insertTimeChanged.connect(lambda _: self.updateInsertTime())
        self.xOffsetChanged.connect(lambda _: self.updateInsertTime())
        self.scaleXChanged.connect(lambda _: self.updateInsertTime())

        self.setCurrentChannel(
            self.get_session_value(self.__session_prefix + 'current-channel', 0))
        self.currentChannelChanged.connect(
            functools.partial(self.set_session_value, self.__session_prefix + 'current-channel'))

        self.setFocusPolicy(Qt.StrongFocus)

        self.__current_channel_action_group = QtWidgets.QActionGroup(self)
        self.__current_channel_action_group.setExclusive(True)
        self.__current_channel_action_group.triggered.connect(
            lambda action: self.setCurrentChannel(action.data()))

        self.set_current_channel_actions = []  # type: List[QtWidgets.QAction]
        for ch in range(16):
            action = QtWidgets.QAction(self)
            action.setData(ch)
            action.setCheckable(True)
            action.setText("Channel %d" % (ch + 1))
            pixmap = QtGui.QPixmap(16, 16)
            pixmap.fill(pianoroll.PianoRollGrid.channel_base_colors[ch])
            icon = QtGui.QIcon(pixmap)
            action.setIcon(icon)
            action.setShortcut(QtGui.QKeySequence(
                ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                 'shift+1', 'shift+2', 'shift+3', 'shift+4', 'shift+5', 'shift+6',
                ][ch]))
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            action.setShortcutVisibleInContextMenu(True)
            self.__current_channel_action_group.addAction(action)
            self.set_current_channel_actions.append(action)
            self.addAction(action)

        self.set_current_channel_actions[self.currentChannel()].setChecked(True)
        self.currentChannelChanged.connect(
            lambda ch: self.set_current_channel_actions[ch].setChecked(True))

        selected_ids = {
            int(segment_id)
            for segment_id in self.get_session_value(
                self.__session_prefix + 'selected-segments', '').split(',')
            if segment_id
        }
        for segment in self.segments:
            if segment.segmentRef().id in selected_ids:
                segment.setSelected(True)
                self.__selection.add(segment.segmentRef().id)
        self.setCanCopy(bool(self.__selection))
        self.setCanCut(bool(self.__selection))

    @property
    def track(self) -> model.PianoRollTrack:
        return down_cast(model.PianoRollTrack, super().track)

    def createToolBox(self) -> tools.ToolBox:
        toolbox = tools.ToolBox(track=self, context=self.context)
        toolbox.addTool(ArrangeSegmentsTool)
        toolbox.addTool(EditEventsTool)
        toolbox.addTool(SelectEventsTool)
        toolbox.addTool(EditVelocityTool)
        return toolbox

    def __addSegment(self, insert_index: int, segment_ref: model.PianoRollSegmentRef) -> None:
        seditor = SegmentEditor(track_editor=self, segment_ref=segment_ref, context=self.context)
        self.__segment_map[segment_ref.id] = seditor
        self.segments.insert(insert_index, seditor)

        seditor.setEnabled(self.isCurrent())
        seditor.setScaleX(self.scaleX())
        self.scaleXChanged.connect(seditor.setScaleX)
        seditor.setYOffset(self.yOffset())
        self.yOffsetChanged.connect(seditor.setYOffset)
        seditor.setGridYSize(self.gridYSize())
        self.gridYSizeChanged.connect(seditor.setGridYSize)
        seditor.setCurrentChannel(self.currentChannel())
        self.currentChannelChanged.connect(seditor.setCurrentChannel)
        seditor.setInsertVelocity(self.__velocity.value())
        self.__velocity.valueChanged.connect(seditor.setInsertVelocity)
        seditor.playNotes.connect(self.playNotes)
        self.repositionSegment(seditor, seditor.startTime(), seditor.endTime())
        seditor.setSelected(segment_ref.id in self.__selection)
        down_cast(PianoRollToolMixin, self.currentTool()).activateSegment(seditor)

        for segment in self.segments:
            segment.raise_()
        self.__insert_cursor.raise_()
        self.__keys.raise_()
        self.__velocity_group.raise_()
        self.__y_scrollbar.raise_()

        self.update()

    def __removeSegment(self, remove_index: int, segment_ref: model.PianoRollSegmentRef) -> None:
        seditor = self.segments.pop(remove_index)
        del self.__segment_map[seditor.segmentRef().id]
        seditor.cleanup()
        seditor.hide()
        seditor.setParent(None)
        self.update()

    def __segmentsChanged(
            self, change: music.PropertyListChange[model.PianoRollSegmentRef]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addSegment(change.index, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__removeSegment(change.index, change.old_value)

        else:
            raise TypeError(type(change))

    def __hoverPitchChanged(self, pitch: int) -> None:
        if self.__hover_pitch >= 0:
            self.__keys.noteOff(self.__hover_pitch)

        self.__hover_pitch = pitch
        if self.__hover_pitch >= 0:
            self.__keys.noteOn(self.__hover_pitch)

    def setIsCurrent(self, is_current: bool) -> None:
        super().setIsCurrent(is_current)
        for segment in self.segments:
            segment.setEnabled(is_current)

    def __selectionChanged(self) -> None:
        self.set_session_value(
            self.__session_prefix + 'selected-segments',
            ','.join(str(segment_id) for segment_id in sorted(self.__selection)))
        self.setCanCut(bool(self.__selection))
        self.setCanCopy(bool(self.__selection))

    def addToSelection(self, segment: SegmentEditor) -> None:
        self.__selection.add(segment.segmentRef().id)
        self.__last_selected = segment
        segment.setSelected(True)
        self.__selectionChanged()

    def removeFromSelection(self, segment: SegmentEditor) -> None:
        self.__selection.discard(segment.segmentRef().id)
        if segment is self.__last_selected:
            self.__last_selected = None
        segment.setSelected(False)
        self.__selectionChanged()

    def clearSelection(self) -> None:
        for segment in self.selection():
            segment.setSelected(False)
        self.__selection.clear()
        self.__last_selected = None
        self.__selectionChanged()

    def lastSelected(self) -> SegmentEditor:
        return self.__last_selected

    def numSelected(self) -> int:
        return len(self.__selection)

    def selection(self) -> List[SegmentEditor]:
        segments = []  # type: List[SegmentEditor]
        for segment in self.segments:
            if segment.segmentRef().id in self.__selection:
                segments.append(segment)

        return segments

    def copyToClipboard(self) -> music.ClipboardContents:
        segments = self.selection()
        assert len(segments) > 0

        segment_data = self.track.copy_segments(
            [segment.segmentRef() for segment in segments])

        self.setInsertTime(max(segment.endTime() for segment in segments))

        data = music.ClipboardContents()
        data.Extensions[clipboard_pb2.pianoroll_segments].CopyFrom(segment_data)
        return data

    def cutToClipboard(self) -> music.ClipboardContents:
        segments = self.selection()
        assert len(segments) > 0

        with self.project.apply_mutations('%s: cut segment(s)' % self.track.name):
            segment_data = self.track.cut_segments(
                [segment.segmentRef() for segment in segments])
        self.clearSelection()

        self.setInsertTime(min(segment.startTime() for segment in segments))

        data = music.ClipboardContents()
        data.Extensions[clipboard_pb2.pianoroll_segments].CopyFrom(segment_data)
        return data

    def canPaste(self, data: music.ClipboardContents) -> bool:
        return data.HasExtension(clipboard_pb2.pianoroll_segments)

    def pasteFromClipboard(self, data: music.ClipboardContents) -> None:
        assert data.HasExtension(clipboard_pb2.pianoroll_segments)
        segment_data = data.Extensions[clipboard_pb2.pianoroll_segments]

        time = self.insertTime()
        if time < audioproc.MusicalTime(0, 1):
            time = audioproc.MusicalTime(0, 1)

        with self.project.apply_mutations('%s: paste segment(s)' % self.track.name):
            segments = self.track.paste_segments(segment_data, time)

        self.setInsertTime(max(segment.end_time for segment in segments))

        self.clearSelection()
        for segment in segments:
            self.addToSelection(self.__segment_map[segment.id])

    def canPasteAsLink(self, data: music.ClipboardContents) -> bool:
        if not data.HasExtension(clipboard_pb2.pianoroll_segments):
            return False

        existing_segments = {segment.id for segment in self.track.segment_heap}
        segment_data = data.Extensions[clipboard_pb2.pianoroll_segments]
        for serialized_ref in segment_data.segment_refs:
            if serialized_ref.segment not in existing_segments:
                return False

        return True

    def pasteAsLinkFromClipboard(self, data: music.ClipboardContents) -> None:
        assert data.HasExtension(clipboard_pb2.pianoroll_segments)
        segment_data = data.Extensions[clipboard_pb2.pianoroll_segments]

        time = self.insertTime()
        if time < audioproc.MusicalTime(0, 1):
            time = audioproc.MusicalTime(0, 1)

        with self.project.apply_mutations('%s: link segment(s)' % self.track.name):
            segments = self.track.link_segments(segment_data, time)

        self.setInsertTime(max(segment.end_time for segment in segments))

        self.clearSelection()
        for segment in segments:
            self.addToSelection(self.__segment_map[segment.id])

    def updatePlaybackPosition(self) -> None:
        time = self.playbackPosition()
        for segment in self.segments:
            if segment.startTime() <= time < segment.endTime():
                segment.setPlaybackPosition(time.relative_to(segment.startTime()))
            else:
                segment.setPlaybackPosition(audioproc.MusicalTime(-1, 1))

    def updateInsertTime(self) -> None:
        time = self.insertTime()
        if time < audioproc.MusicalTime(0, 1):
            self.__insert_cursor.hide()
            return

        x = self.timeToX(time) - self.xOffset() - 1
        if not -3 < x <= self.width():
            self.__insert_cursor.hide()
            return

        self.__insert_cursor.setGeometry(x, 0, 3, self.height())
        self.__insert_cursor.show()

    def gridStep(self) -> audioproc.MusicalDuration:
        for s in (64, 32, 16, 8, 4, 2):
            if self.scaleX() / s > 96:
                return audioproc.MusicalDuration(1, s)
        return audioproc.MusicalDuration(1, 1)

    def gridHeight(self) -> int:
        return 128 * self.gridYSize() + 1

    def repositionSegment(
            self,
            segment: SegmentEditor,
            start_time: audioproc.MusicalTime,
            end_time: audioproc.MusicalTime
    ) -> None:
        x1 = self.timeToX(start_time)
        x2 = self.timeToX(end_time) + 1

        rect = QtCore.QRect(x1, 0, x2 - x1, self.height())
        rect.translate(-self.xOffset(), 0)
        clipped_rect = rect.intersected(QtCore.QRect(0, 0, self.width(), self.height()))
        if not clipped_rect.isEmpty():
            segment.setXOffset(max(0, -rect.left()))
            segment.setGeometry(clipped_rect)
            segment.show()
        else:
            segment.hide()

    def __repositionSegments(self) -> None:
        for segment in self.segments:
            self.repositionSegment(segment, segment.startTime(), segment.endTime())

    def segmentAt(self, x: int) -> 'SegmentEditor':
        return self.segmentAtTime(self.xToTime(x))

    def segmentAtTime(self, time: audioproc.MusicalTime) -> 'SegmentEditor':
        for seditor in reversed(self.segments):
            if seditor.startTime() <= time < seditor.endTime():
                return seditor
        return None

    def __updateYScrollbar(self) -> None:
        self.__y_scrollbar.setRange(0, max(0, self.gridHeight() - self.height()))
        self.__y_scrollbar.setPageStep(self.height())

    def shouldSnap(self, evt: QtGui.QMouseEvent) -> bool:
        return self.snapToGrid() and not evt.modifiers() & Qt.ShiftModifier

    def snapTime(self, time: audioproc.MusicalTime) -> audioproc.MusicalTime:
        grid_time = (
            audioproc.MusicalTime(0, 1)
            + self.gridStep() * int(round(float(time / self.gridStep()))))
        time_x = int(time * self.scaleX())
        grid_x = int(grid_time * self.scaleX())
        if abs(time_x - grid_x) <= 10:
            return grid_time
        return time

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        self.__keys.move(0, 0)
        self.__keys.resize(self.__keys.width(), self.height())

        self.__velocity_group.move(self.__keys.width(), 0)

        self.__y_scrollbar.move(self.width() - self.__y_scrollbar.width(), 0)
        self.__y_scrollbar.resize(self.__y_scrollbar.width(), self.height())

        self.__updateYScrollbar()
        self.__repositionSegments()

    def showEvent(self, evt: QtGui.QShowEvent) -> None:
        super().showEvent(evt)

        if self.__first_show:
            self.setGridYSize(self.get_session_value(self.__session_prefix + 'grid-y-size', 15))
            self.gridYSizeChanged.connect(
                functools.partial(self.set_session_value, self.__session_prefix + 'grid-y-size'))

            default_y_offset = max(0, min(self.gridHeight() - self.height(),
                                          self.gridHeight() - self.height()) // 2)
            self.setYOffset(self.get_session_value(
                self.__session_prefix + 'y-offset', default_y_offset))
            self.yOffsetChanged.connect(
                functools.partial(self.set_session_value, self.__session_prefix + 'y-offset'))

            self.__first_show = False

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        if evt.modifiers() == Qt.NoModifier:
            offset = self.yOffset()
            if evt.angleDelta().y() > 0:
                offset -= 3 * self.gridYSize()
            elif evt.angleDelta().y() < 0:
                offset += 3 * self.gridYSize()
            offset = min(self.gridHeight() - self.height(), offset)
            offset = max(0, offset)
            if offset != self.yOffset():
                self.setYOffset(offset)
                evt.accept()
                return

        super().wheelEvent(evt)

    def _paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        painter.setPen(Qt.black)

        beat_time = audioproc.MusicalTime()
        beat_num = 0
        while beat_time < self.projectEndTime():
            x = self.timeToX(beat_time)

            if beat_num == 0:
                painter.fillRect(x, 0, 2, self.height(), Qt.black)
            else:
                if beat_time % audioproc.MusicalTime(1, 4) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(160, 160, 160)
                elif beat_time % audioproc.MusicalTime(1, 8) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(185, 185, 185)
                elif beat_time % audioproc.MusicalTime(1, 16) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(210, 210, 210)
                elif beat_time % audioproc.MusicalTime(1, 32) == audioproc.MusicalTime(0, 1):
                    c = QtGui.QColor(225, 225, 225)
                else:
                    c = QtGui.QColor(240, 240, 240)

                painter.fillRect(x, 0, 1, self.height(), c)

            beat_time += self.gridStep()
            beat_num += 1

        x = self.timeToX(self.projectEndTime())
        painter.fillRect(x, 0, 2, self.height(), Qt.black)

    def playNotes(self, play_notes: pianoroll.PlayNotes) -> None:
        if self.playerState().playerID():
            for channel, pitch in play_notes.note_off:
                if (channel, pitch) in self.__active_notes:
                    self.call_async(self.project_view.sendNodeMessage(
                        processor_messages.note_off_event(
                            self.track.pipeline_node_id, channel, pitch)))

                    self.__active_notes.discard((channel, pitch))

            if play_notes.all_notes_off:
                for channel, pitch in self.__active_notes:
                    self.call_async(self.project_view.sendNodeMessage(
                        processor_messages.note_off_event(
                            self.track.pipeline_node_id, channel, pitch)))

                self.__active_notes.clear()

            for channel, pitch in play_notes.note_on:
                self.call_async(self.project_view.sendNodeMessage(
                    processor_messages.note_on_event(
                        self.track.pipeline_node_id, channel, pitch, 100)))

                self.__active_notes.add((channel, pitch))
