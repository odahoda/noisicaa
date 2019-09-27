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
import itertools
import logging
from typing import Any, Optional, Union, Dict, List, Set, Type

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa import value_types
from noisicaa.music import base_track_pb2
from noisicaa.ui import ui_base
from noisicaa.ui import clipboard
from noisicaa.ui import slots
from . import base_track_editor
from . import tools

# TODO: These would create cyclic import dependencies.
Editor = Any


logger = logging.getLogger(__name__)


class BaseMeasureEditor(ui_base.ProjectMixin, QtCore.QObject):
    rectChanged = QtCore.pyqtSignal(QtCore.QRect)

    def __init__(self, track_editor: 'MeasuredTrackEditor', **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__top_left = QtCore.QPoint()
        self.__playback_time = None  # type: audioproc.MusicalTime
        self.__track_editor = track_editor

    def cleanup(self) -> None:
        pass

    @property
    def track_editor(self) -> 'MeasuredTrackEditor':
        return self.__track_editor

    @property
    def track(self) -> music.MeasuredTrack:
        return down_cast(music.MeasuredTrack, self.__track_editor.track)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        raise NotImplementedError

    @property
    def index(self) -> int:
        for idx, meditor in enumerate(self.__track_editor.measure_editors()):
            if meditor is self:
                return idx
        raise ValueError

    @property
    def next_sibling(self) -> 'BaseMeasureEditor':
        return self.__track_editor.measure_editors()[self.index + 1]

    def topLeft(self) -> QtCore.QPoint:
        return self.__top_left

    def setTopLeft(self, pos: QtCore.QPoint) -> None:
        self.__top_left = QtCore.QPoint(pos)

    def scaleX(self) -> fractions.Fraction:
        return self.track_editor.scaleX()

    def width(self) -> int:
        raise NotImplementedError

    def height(self) -> int:
        return self.track_editor.height()

    def size(self) -> QtCore.QSize:
        return QtCore.QSize(self.width(), self.height())

    def rect(self) -> QtCore.QRect:
        return QtCore.QRect(0, 0, self.width(), self.height())

    def viewRect(self) -> QtCore.QRect:
        return QtCore.QRect(self.topLeft(), self.size())

    def playbackPos(self) -> audioproc.MusicalTime:
        return self.__playback_time

    def clearPlaybackPos(self) -> None:
        self.__playback_time = None
        self.rectChanged.emit(self.viewRect())

    def setPlaybackPos(self, time: audioproc.MusicalTime) -> None:
        self.__playback_time = time
        self.rectChanged.emit(self.viewRect())

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        pass

    def purgePaintCaches(self) -> None:
        pass

    def invalidatePaintCache(self, *layers: str) -> None:
        pass

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        raise NotImplementedError

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        pass

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        pass


class MeasureEditor(core.AutoCleanupMixin, slots.SlotContainer, BaseMeasureEditor):
    selected, setSelected, selectedChanged = slots.slot(bool, 'selected', default=False)

    PLAYBACK_POS = 'playback_pos'

    layers = None  # type: List[str]

    def __init__(self, measure_reference: music.MeasureReference, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__paint_caches = {}  # type: Dict[str, QtGui.QPixmap]
        self.__cached_size = QtCore.QSize()

        self.__measure_reference = measure_reference

        self.__measure = self.__measure_reference.measure
        self.__measure_listener = self.__measure_reference.measure_changed.add(
            self.__measureChanged)

        self.__hovered = False

        self._measure_listeners = core.ListenerList()
        self.add_cleanup_function(self._measure_listeners.cleanup)

        if self.__measure is not None:
            self.addMeasureListeners()

        self.selectedChanged.connect(lambda _: self.rectChanged.emit(self.viewRect()))

        self.track_editor.hoveredMeasureChanged.connect(self.__onHoveredMeasureChanged)

    def cleanup(self) -> None:
        self.track_editor.hoveredMeasureChanged.disconnect(self.__onHoveredMeasureChanged)

        super().cleanup()

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self.__measure.duration

    @property
    def measure_reference(self) -> music.MeasureReference:
        return self.__measure_reference

    @property
    def measure(self) -> music.Measure:
        return self.__measure

    @property
    def is_first(self) -> bool:
        return (
            self.__measure_reference is not None
            and self.__measure_reference.index == 0)

    def width(self) -> int:
        return int(self.scaleX() * self.measure.duration.fraction)

    def addMeasureListeners(self) -> None:
        raise NotImplementedError

    def __measureChanged(self, change: music.PropertyValueChange[music.Measure]) -> None:
        self._measure_listeners.cleanup()

        self.purgePaintCaches()

        self.__measure = self.__measure_reference.measure
        self.addMeasureListeners()

        self.rectChanged.emit(self.viewRect())

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        super().buildContextMenu(menu, pos)

        insert_measure_action = QtWidgets.QAction("Insert measure", menu)
        insert_measure_action.setStatusTip("Insert an empty measure at this point.")
        insert_measure_action.triggered.connect(self.onInsertMeasure)
        menu.addAction(insert_measure_action)

        remove_measure_action = QtWidgets.QAction("Remove measure", menu)
        remove_measure_action.setStatusTip("Remove this measure.")
        remove_measure_action.triggered.connect(self.onRemoveMeasure)
        menu.addAction(remove_measure_action)

    def onInsertMeasure(self) -> None:
        with self.project.apply_mutations('%s: Insert measure' % self.track.name):
            self.track.insert_measure(self.measure_reference.index)

    def onRemoveMeasure(self) -> None:
        with self.project.apply_mutations('%s: Remove measure' % self.track.name):
            self.track.remove_measure(self.measure_reference.index)

    def __onHoveredMeasureChanged(self, measure_id: int) -> None:
        hovered = (measure_id == self.measure_reference.measure.id)
        if hovered != self.__hovered:
            self.__hovered = hovered
            self.rectChanged.emit(self.viewRect())

    def purgePaintCaches(self) -> None:
        self.__paint_caches.clear()

    def invalidatePaintCache(self, *layers: str) -> None:
        for layer in layers:
            self.__paint_caches.pop(layer, None)
        self.rectChanged.emit(self.viewRect())

    def paintPlaybackPos(self, painter: QtGui.QPainter) -> None:
        raise NotImplementedError

    def paintLayer(self, layer: str, painter: QtGui.QPainter) -> None:
        raise NotImplementedError

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        if self.__cached_size != self.size():
            self.__paint_caches.clear()

        for layer in self.layers:
            if layer == self.PLAYBACK_POS:
                continue
            if layer not in self.__paint_caches:
                pixmap = QtGui.QPixmap(self.size())
                pixmap.fill(Qt.transparent)
                layer_painter = QtGui.QPainter(pixmap)
                try:
                    self.paintLayer(layer, layer_painter)
                finally:
                    layer_painter.end()

                self.__paint_caches[layer] = pixmap

        self.__cached_size = self.size()

        if self.selected():
            painter.fillRect(paint_rect, QtGui.QColor(255, 200, 200))
        elif self.__hovered:
            painter.fillRect(paint_rect, QtGui.QColor(220, 220, 255))

        for layer in self.layers:
            if layer == self.PLAYBACK_POS:
                if self.playbackPos() is not None:
                    self.paintPlaybackPos(painter)
            else:
                painter.drawPixmap(0, 0, self.__paint_caches[layer])


class Appendix(BaseMeasureEditor):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__hover = False

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(1, 1)

    def setHover(self, hover: bool) -> None:
        if hover != self.__hover:
            self.__hover = hover
            self.rectChanged.emit(self.viewRect())

    def clickRect(self) -> QtCore.QRect:
        ymid = self.height() // 2
        y1 = max(5, ymid - 40)
        y2 = min(self.height() - 5, ymid + 40)
        return QtCore.QRect(10, y1, 80, y2 - y1 + 1)

    def width(self) -> int:
        return 90

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        click_rect = self.clickRect()
        if click_rect.height() > 20:
            if self.__hover:
                painter.fillRect(click_rect, QtGui.QColor(255, 200, 200))

            x1 = click_rect.left()
            x2 = click_rect.right()
            y1 = click_rect.top()
            y2 = click_rect.bottom()
            painter.setPen(QtGui.QColor(200, 200, 200))
            painter.drawLine(x1, y1, x2, y1)
            painter.drawLine(x2, y1, x2, y2)
            painter.drawLine(x2, y2, x1, y2)
            painter.drawLine(x1, y2, x1, y1)

        if self.playbackPos() is not None:
            pos = int(self.width() * (self.playbackPos() / self.duration).fraction)
            painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHover(False)
        super().leaveEvent(evt)


class MeasuredTrackToolBase(clipboard.CopyableMixin, tools.ToolBase):  # pylint: disable=abstract-method
    track = None  # type: MeasuredTrackEditor

    def onSetTimeSignature(
            self,
            affected_measure_editors: List[MeasureEditor],
            time_signature: value_types.TimeSignature
    ) -> None:
        with self.project.apply_mutations('%s: Change time signature' % self.track.track.name):
            for meditor in affected_measure_editors:
                meditor.measure.time_signature = time_signature

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        affected_measure_editors = []  # type: List[MeasureEditor]
        if self.track.numSelected() > 0:
            affected_measure_editors.extend(self.track.selection())
        else:
            meditor = self.track.measureEditorAt(pos)
            if isinstance(meditor, MeasureEditor):
                affected_measure_editors.append(meditor)

        enable_measure_actions = bool(affected_measure_editors)

        time_signature_menu = menu.addMenu("Set time signature")
        time_signatures = [
            value_types.TimeSignature(4, 4),
            value_types.TimeSignature(3, 4),
        ]
        for time_signature in time_signatures:
            time_signature_action = QtWidgets.QAction(
                "%d/%d" % (time_signature.upper, time_signature.lower),
                menu)
            time_signature_action.setEnabled(enable_measure_actions)
            time_signature_action.triggered.connect(
                lambda _, time_signature=time_signature: (
                    self.onSetTimeSignature(affected_measure_editors, time_signature)))
            time_signature_menu.addAction(time_signature_action)

        measure_editor = self.track.measureEditorAt(pos)
        if measure_editor is not None:
            measure_editor.buildContextMenu(
                menu, pos - measure_editor.topLeft())

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu(self.track)
        menu.setObjectName('context-menu')
        self.buildContextMenu(menu, evt.pos())
        menu.popup(evt.globalPos())
        evt.accept()


class MeasuredToolBase(MeasuredTrackToolBase):  # pylint: disable=abstract-method
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__mouse_grabber = None  # type: BaseMeasureEditor
        self.__mouse_pos = None  # type: QtCore.QPoint

    def _measureEditorUnderMouse(self) -> BaseMeasureEditor:
        if self.__mouse_pos is None:
            return None
        return self.track.measureEditorAt(self.__mouse_pos)

    def __makeMouseEvent(
            self, measure_editor: BaseMeasureEditor, evt: QtGui.QMouseEvent
    ) -> QtGui.QMouseEvent:
        measure_evt = QtGui.QMouseEvent(
            evt.type(),
            evt.localPos() - measure_editor.topLeft(),
            evt.windowPos(),
            evt.screenPos(),
            evt.button(),
            evt.buttons(),
            evt.modifiers())
        measure_evt.setAccepted(False)
        return measure_evt

    def mousePressMeasureEvent(self, measure: BaseMeasureEditor, evt: QtGui.QMouseEvent) -> None:
        pass

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()

        measure_editor = self.track.measureEditorAt(evt.pos())
        if isinstance(measure_editor, MeasureEditor):
            measure_evt = self.__makeMouseEvent(measure_editor, evt)
            self.mousePressMeasureEvent(measure_editor, measure_evt)
            if measure_evt.isAccepted():
                self.__mouse_grabber = measure_editor
            evt.setAccepted(measure_evt.isAccepted())

        elif isinstance(measure_editor, Appendix):
            if measure_editor.clickRect().contains(evt.pos() - measure_editor.topLeft()):
                with self.project.apply_mutations('%s: Insert measure' % self.track.track.name):
                    self.track.track.insert_measure(-1)
                evt.accept()
                return

    def mouseReleaseMeasureEvent(self, measure: BaseMeasureEditor, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()

        if isinstance(self.__mouse_grabber, MeasureEditor):
            measure_evt = self.__makeMouseEvent(self.__mouse_grabber, evt)
            self.mouseReleaseMeasureEvent(self.__mouse_grabber, measure_evt)
            self.__mouse_grabber = None
            evt.setAccepted(measure_evt.isAccepted())
            self.track.setHoverMeasureEditor(self.track.measureEditorAt(evt.pos()), evt)

    def mouseMoveMeasureEvent(self, measure: BaseMeasureEditor, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()

        if self.__mouse_grabber is not None:
            measure_editor = self.__mouse_grabber
        else:
            measure_editor = self.track.measureEditorAt(evt.pos())
            self.track.setHoverMeasureEditor(measure_editor, evt)

        if isinstance(measure_editor, MeasureEditor):
            measure_evt = self.__makeMouseEvent(measure_editor, evt)
            self.mouseMoveMeasureEvent(measure_editor, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

        elif isinstance(measure_editor, Appendix):
            measure_editor.setHover(
                measure_editor.clickRect().contains(evt.pos() - measure_editor.topLeft()))

    def mouseDoubleClickMeasureEvent(
            self, measure: BaseMeasureEditor, evt: QtGui.QMouseEvent) -> None:
        pass

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()

        measure_editor = self.track.measureEditorAt(evt.pos())
        if isinstance(measure_editor, MeasureEditor):
            measure_evt = self.__makeMouseEvent(measure_editor, evt)
            self.mouseDoubleClickMeasureEvent(measure_editor, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def wheelMeasureEvent(self, measure: BaseMeasureEditor, evt: QtGui.QWheelEvent) -> None:
        pass

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        self.__mouse_pos = evt.pos()

        measure_editor = self.track.measureEditorAt(evt.pos())
        if isinstance(measure_editor, MeasureEditor):
            measure_evt = QtGui.QWheelEvent(
                evt.pos() - measure_editor.topLeft(),
                evt.globalPos(),
                evt.pixelDelta(),
                evt.angleDelta(),
                0,
                Qt.Horizontal,
                evt.buttons(),
                evt.modifiers(),
                evt.phase(),
                evt.source())
            measure_evt.setAccepted(False)
            self.wheelMeasureEvent(measure_editor, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def __makeKeyEvent(
            self, measure_editor: BaseMeasureEditor, evt: QtGui.QKeyEvent) -> QtGui.QKeyEvent:
        measure_evt = QtGui.QKeyEvent(
            evt.type(),
            evt.key(),
            evt.modifiers(),
            evt.nativeScanCode(),
            evt.nativeVirtualKey(),
            evt.nativeModifiers(),
            evt.text(),
            evt.isAutoRepeat(),
            evt.count())
        measure_evt.setAccepted(False)
        return measure_evt

    def keyPressMeasureEvent(self, measure: BaseMeasureEditor, evt: QtGui.QKeyEvent) -> None:
        pass

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        measure_editor = self._measureEditorUnderMouse()
        if isinstance(measure_editor, MeasureEditor):
            measure_evt = self.__makeKeyEvent(measure_editor, evt)
            self.keyPressMeasureEvent(measure_editor, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def keyReleaseMeasureEvent(self, measure: BaseMeasureEditor, evt: QtGui.QKeyEvent) -> None:
        pass

    def _keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        measure_editor = self._measureEditorUnderMouse()
        if isinstance(measure_editor, MeasureEditor):
            measure_evt = self.__makeKeyEvent(measure_editor, evt)
            self.keyReleaseMeasureEvent(measure_editor, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())


class ArrangeMeasuresTool(MeasuredTrackToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.ARRANGE_MEASURES,
            group=tools.ToolGroup.ARRANGE,
            **kwargs)

        self.__selection_first = None  # type: MeasureEditor
        self.__selection_last = None  # type: MeasureEditor

        self.track.selectionChanged.connect(self.__selectionChanged)

    def deactivated(self) -> None:
        self.track.clearSelection()
        super().deactivated()

    def iconName(self) -> str:
        return 'pointer'

    def __selectionChanged(self) -> None:
        num_selected = self.track.numSelected()
        self.setCanCopy(num_selected > 0)
        self.setCanCut(False)

    def copyToClipboard(self) -> music.ClipboardContents:
        measures = self.track.selection()
        assert len(measures) > 0

        measures_data = self.track.track.copy_measures(
            [measure.measure_reference for measure in measures])
        measures_data.type = self.track.measure_type

        data = music.ClipboardContents()
        data.Extensions[base_track_pb2.measures].CopyFrom(measures_data)
        return data

    def cutToClipboard(self) -> music.ClipboardContents:
        return None

    def canPaste(self, data: music.ClipboardContents) -> bool:
        if self.track.numSelected() == 0:
            return False
        if not data.HasExtension(base_track_pb2.measures):
            return False
        measures_data = data.Extensions[base_track_pb2.measures]
        return measures_data.type == self.track.measure_type

    def pasteFromClipboard(self, data: music.ClipboardContents) -> None:
        assert data.HasExtension(base_track_pb2.measures)
        measures_data = data.Extensions[base_track_pb2.measures]
        assert measures_data.type == self.track.measure_type
        refs = self.track.selection()
        assert refs

        with self.project.apply_mutations('%s: paste measures(s)' % self.track.track.name):
            self.track.track.paste_measures(
                measures_data,
                min(ref.index for ref in refs),
                max(ref.index for ref in refs))

    def canPasteAsLink(self, data: music.ClipboardContents) -> bool:
        if self.track.numSelected() == 0:
            return False
        if not data.HasExtension(base_track_pb2.measures):
            return False
        measures_data = data.Extensions[base_track_pb2.measures]
        return measures_data.type == self.track.measure_type

    def pasteAsLinkFromClipboard(self, data: music.ClipboardContents) -> None:
        assert data.HasExtension(base_track_pb2.measures)
        measures_data = data.Extensions[base_track_pb2.measures]
        assert measures_data.type == self.track.measure_type
        refs = self.track.selection()
        assert refs

        with self.project.apply_mutations('%s: paste measures(s)' % self.track.track.name):
            self.track.track.link_measures(
                measures_data,
                min(ref.index for ref in refs),
                max(ref.index for ref in refs))

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            measure_editor = self.track.measureEditorAt(evt.pos())

            if isinstance(measure_editor, MeasureEditor):
                self.track.clearSelection()

                self.track.addToSelection(measure_editor)
                self.__selection_first = measure_editor
                self.__selection_last = None
                evt.accept()
                return

        # TODO: handle click on appendix
        super().mousePressEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.__selection_first = None
            self.__selection_last = None
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        measure_editor = self.track.measureEditorAt(evt.pos())
        self.track.setHoverMeasureEditor(measure_editor, evt)

        if self.__selection_first is not None and isinstance(measure_editor, MeasureEditor):
            start_idx = self.__selection_first.measure_reference.index
            last_idx = measure_editor.measure_reference.index

            if start_idx > last_idx:
                start_idx, last_idx = last_idx, start_idx

            for meditor in itertools.islice(self.track.measure_editors(), start_idx, last_idx + 1):
                if isinstance(meditor, MeasureEditor) and not meditor.selected():
                    self.track.addToSelection(meditor)

            for seditor in self.track.selection():
                if (not (start_idx <= seditor.measure_reference.index <= last_idx)
                        and seditor.selected()):
                    self.track.removeFromSelection(seditor)

            self.__selection_last = measure_editor

            evt.accept()
            return

        super().mouseMoveEvent(evt)


class MeasuredTrackEditor(  # pylint: disable=abstract-method
        clipboard.CopyableDelegatorMixin,
        base_track_editor.BaseTrackEditor):
    hoveredMeasureChanged = QtCore.pyqtSignal(int)
    selectionChanged = QtCore.pyqtSignal()

    measure_type = None  # type: str
    measure_editor_cls = None  # type: Type[MeasureEditor]

    def __init__(self, **kwargs: Any) -> None:
        self.__measure_editors = []  # type: List[BaseMeasureEditor]

        super().__init__(**kwargs)

        self.setFocusPolicy(Qt.StrongFocus)

        self.__closing = False
        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__selection = set()  # type: Set[int]
        self.__measure_editor_at_playback_pos = None  # type: BaseMeasureEditor
        self.__hover_measure_editor = None  # type: BaseMeasureEditor

        for idx, mref in enumerate(self.track.measure_list):
            self.addMeasure(idx, mref)

        appendix_editor = Appendix(track_editor=self, context=self.context)
        appendix_editor.rectChanged.connect(self.update)
        self.__measure_editors.append(appendix_editor)

        self.__listeners.add(self.track.measure_list_changed.add(self.onMeasureListChanged))

        self.updateMeasures()

        self.playbackPositionChanged.connect(self.__playbackPositionChanged)

        self.__currentToolChanged(self.currentToolType())
        self.currentToolChanged.connect(self.__currentToolChanged)

    def cleanup(self) -> None:
        self.__closing = True

        while len(self.__measure_editors) > 0:
            self.removeMeasure(0)

        super().cleanup()

    @property
    def track(self) -> music.MeasuredTrack:
        return down_cast(music.MeasuredTrack, super().track)

    def measure_editors(self) -> List[BaseMeasureEditor]:
        return self.__measure_editors

    def addToSelection(self, measure: MeasureEditor) -> None:
        if measure.selected():
            return

        self.__selection.add(measure.measure_reference.id)
        measure.setSelected(True)
        self.selectionChanged.emit()

    def removeFromSelection(self, measure: MeasureEditor) -> None:
        if not measure.selected():
            return

        measure.setSelected(False)
        self.__selection.discard(measure.measure_reference.id)
        self.selectionChanged.emit()

    def clearSelection(self) -> None:
        if not self.__selection:
            return

        for measure in self.__measure_editors:
            if isinstance(measure, MeasureEditor):
                measure.setSelected(False)
        self.__selection.clear()
        self.selectionChanged.emit()

    def numSelected(self) -> int:
        return len(self.__selection)

    def selection(self) -> List[MeasureEditor]:
        measures = []  # type: List[MeasureEditor]
        for measure in self.__measure_editors:
            if (isinstance(measure, MeasureEditor)
                    and measure.measure_reference.id in self.__selection):
                measures.append(measure)
        return measures

    def onMeasureListChanged(
            self, change: music.PropertyListChange[music.MeasureReference]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.addMeasure(change.index, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.removeMeasure(change.index)

        else:
            raise TypeError(type(change))

    def addMeasure(self, idx: int, mref: music.MeasureReference) -> None:
        measure_editor = self.measure_editor_cls(  # pylint: disable=not-callable
            track_editor=self, measure_reference=mref, context=self.context)
        measure_editor.rectChanged.connect(self.update)
        self.__measure_editors.insert(idx, measure_editor)
        self.updateMeasures()
        self.update()

    def removeMeasure(self, idx: int) -> None:
        measure_editor = self.__measure_editors.pop(idx)
        if isinstance(measure_editor, MeasureEditor) and measure_editor.selected():
            self.removeFromSelection(measure_editor)
        measure_editor.cleanup()
        measure_editor.rectChanged.disconnect(self.update)
        self.updateMeasures()
        self.update()

    def updateMeasures(self) -> None:
        if self.__closing:
            return

        p = QtCore.QPoint(self.leftMargin(), 0)
        for measure_editor in self.measure_editors():
            measure_editor.setTopLeft(p)
            p += QtCore.QPoint(measure_editor.width(), 0)

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        super().setScaleX(scale_x)
        self.updateMeasures()

    def __playbackPositionChanged(self, time: audioproc.MusicalTime) -> None:
        if self.__measure_editor_at_playback_pos is not None:
            self.__measure_editor_at_playback_pos.clearPlaybackPos()
            self.__measure_editor_at_playback_pos = None

        measure_time = audioproc.MusicalTime()
        for measure_editor in self.measure_editors():
            if measure_time <= time < measure_time + measure_editor.duration:
                measure_editor.setPlaybackPos(
                    audioproc.MusicalTime() + (time - measure_time))
                self.__measure_editor_at_playback_pos = measure_editor
                break
            measure_time += measure_editor.duration

    def measureEditorAt(self, pos: QtCore.QPoint) -> BaseMeasureEditor:
        p = QtCore.QPoint(self.leftMargin(), 0)
        for measure_editor in self.measure_editors():
            if p.x() <= pos.x() < p.x() + measure_editor.width():
                return measure_editor

            p += QtCore.QPoint(measure_editor.width(), 0)

        return None

    def setHoverMeasureEditor(
            self, measure_editor: Optional[BaseMeasureEditor],
            evt: Union[None, QtGui.QEnterEvent, QtGui.QMouseEvent]
    ) -> None:
        if measure_editor is self.__hover_measure_editor:
            return

        if self.__hover_measure_editor is not None:
            measure_evt = QtCore.QEvent(QtCore.QEvent.Leave)
            self.__hover_measure_editor.leaveEvent(measure_evt)

        if measure_editor is not None:
            measure_evt = QtGui.QEnterEvent(
                evt.localPos() - measure_editor.topLeft(),
                evt.windowPos(),
                evt.screenPos())
            measure_editor.enterEvent(measure_evt)

        self.__hover_measure_editor = measure_editor
        self.hoveredMeasureChanged.emit(
            measure_editor.measure_reference.measure.id
            if self.isCurrent() and isinstance(measure_editor, MeasureEditor)
            else 0)

    def __currentToolChanged(self, tool: tools.ToolType) -> None:
        self.setDelegatedCopyable(down_cast(MeasuredTrackToolBase, self.currentTool()))

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        evt = down_cast(QtGui.QEnterEvent, evt)
        self.setHoverMeasureEditor(self.measureEditorAt(evt.pos()), evt)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverMeasureEditor(None, None)

    def purgePaintCaches(self) -> None:
        super().purgePaintCaches()
        for measure_editor in self.measure_editors():
            measure_editor.purgePaintCaches()

    def _paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        p = QtCore.QPoint(self.leftMargin(), 0)
        for measure_editor in self.measure_editors():
            measure_rect = QtCore.QRect(p.x(), 0, measure_editor.width(), self.height())
            measure_rect = measure_rect.intersected(paint_rect)
            if not measure_rect.isEmpty():
                painter.save()
                try:
                    painter.setClipRect(measure_rect)
                    painter.translate(p)
                    measure_editor.paint(painter, measure_rect.translated(-p))
                finally:
                    painter.restore()
            p += QtCore.QPoint(measure_editor.width(), 0)
