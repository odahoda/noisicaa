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

import fractions
import itertools
import logging
from typing import Any, Optional, Union, Dict, List, Type  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core  # pylint: disable=unused-import
from noisicaa import music
from noisicaa import model
from noisicaa.ui import tools
from noisicaa.ui import ui_base
from noisicaa.ui import selection_set

# TODO: These would create cyclic import dependencies.
PlayerState = Any
Editor = Any


logger = logging.getLogger(__name__)


class BaseTrackItem(ui_base.ProjectMixin, QtCore.QObject):
    rectChanged = QtCore.pyqtSignal(QtCore.QRect)
    sizeChanged = QtCore.pyqtSignal(QtCore.QSize)
    scaleXChanged = QtCore.pyqtSignal(fractions.Fraction)

    def __init__(self, *, track: music.Track, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__track = track
        self.__scale_x = fractions.Fraction(500, 1)
        self.__view_top_left = QtCore.QPoint()
        self.__is_current = False

        self.__size = QtCore.QSize()

    def close(self) -> None:
        pass

    @property
    def track(self) -> music.Track:
        return self.__track

    def scaleX(self) -> fractions.Fraction:
        return self.__scale_x

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        if scale_x == self.__scale_x:
            return

        self.__scale_x = scale_x
        self.updateSize()
        self.purgePaintCaches()
        self.scaleXChanged.emit(self.__scale_x)
        self.rectChanged.emit(self.viewRect())

    def width(self) -> int:
        return self.__size.width()

    def setWidth(self, width: int) -> None:
        self.setSize(QtCore.QSize(width, self.height()))

    def height(self) -> int:
        return self.__size.height()

    def setHeight(self, height: int) -> None:
        self.setSize(QtCore.QSize(self.width(), height))

    def size(self) -> QtCore.QSize:
        return QtCore.QSize(self.__size)

    def setSize(self, size: QtCore.QSize) -> None:
        if size != self.__size:
            self.__size = QtCore.QSize(size)
            self.sizeChanged.emit(self.__size)

    def updateSize(self) -> None:
        pass

    def viewTopLeft(self) -> QtCore.QPoint:
        return self.__view_top_left

    def viewLeft(self) -> int:
        return self.__view_top_left.x()

    def viewTop(self) -> int:
        return self.__view_top_left.y()

    def setViewTopLeft(self, top_left: QtCore.QPoint) -> None:
        self.__view_top_left = QtCore.QPoint(top_left)

    def viewRect(self) -> QtCore.QRect:
        return QtCore.QRect(self.__view_top_left, self.size())

    def isCurrent(self) -> bool:
        return self.__is_current

    def setIsCurrent(self, is_current: bool) -> None:
        if is_current != self.__is_current:
            self.__is_current = is_current
            self.rectChanged.emit(self.viewRect())

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        remove_track_action = QtWidgets.QAction("Remove track", menu)
        remove_track_action.setStatusTip("Remove this track.")
        remove_track_action.triggered.connect(self.onRemoveTrack)
        menu.addAction(remove_track_action)

    def onRemoveTrack(self) -> None:
        self.send_command_async(music.Command(
            target=self.project.id,
            remove_track=music.RemoveTrack(track_id=self.track.id)))

    def purgePaintCaches(self) -> None:
        pass

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        if self.isCurrent():
            painter.fillRect(paint_rect, QtGui.QColor(240, 240, 255))
        else:
            painter.fillRect(paint_rect, Qt.white)

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        pass  # pragma: no coverage

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        pass  # pragma: no coverage

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        pass  # pragma: no coverage

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        pass  # pragma: no coverage

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass  # pragma: no coverage

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        pass  # pragma: no coverage


class BaseTrackEditorItem(BaseTrackItem):
    currentToolChanged = QtCore.pyqtSignal(tools.ToolType)

    toolBoxClass = None  # type: Type[tools.ToolBox]

    def __init__(self, *, player_state: PlayerState, editor: Editor, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__player_state = player_state
        self.__editor = editor

    def toolBox(self) -> tools.ToolBox:
        tool_box = self.__editor.currentToolBox()
        assert isinstance(tool_box, self.toolBoxClass)
        return tool_box

    def currentTool(self) -> tools.ToolBase:
        return self.toolBox().currentTool()

    def currentToolType(self) -> tools.ToolType:
        return self.toolBox().currentToolType()

    def toolBoxMatches(self) -> bool:
        return isinstance(self.__editor.currentToolBox(), self.toolBoxClass)

    def playerState(self) -> PlayerState:
        return self.__player_state

    def setPlaybackPos(self, time: audioproc.MusicalTime) -> None:
        pass

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mouseMoveEvent(self, evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mousePressEvent(self, evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mouseReleaseEvent(self, evt)

    def mouseDoubleClickEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().mouseDoubleClickEvent(self, evt)

    def wheelEvent(self, evt: QtGui.QWheelEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().wheelEvent(self, evt)

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().keyPressEvent(self, evt)

    def keyReleaseEvent(self, evt: QtGui.QKeyEvent) -> None:
        if self.toolBoxMatches():
            self.toolBox().keyReleaseEvent(self, evt)


class BaseMeasureEditorItem(ui_base.ProjectMixin, QtCore.QObject):
    rectChanged = QtCore.pyqtSignal(QtCore.QRect)

    def __init__(self, track_item: BaseTrackEditorItem, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__top_left = QtCore.QPoint()
        self.__playback_time = None  # type: audioproc.MusicalTime
        self.__track_item = track_item

    def close(self) -> None:
        pass

    @property
    def track_item(self) -> BaseTrackEditorItem:
        return self.__track_item

    @property
    def track(self) -> music.MeasuredTrack:
        return down_cast(music.MeasuredTrack, self.__track_item.track)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        raise NotImplementedError

    @property
    def index(self) -> int:
        for idx, mitem in enumerate(self.__track_item.measure_items()):
            if mitem is self:
                return idx
        raise ValueError

    @property
    def next_sibling(self) -> 'BaseMeasureEditorItem':
        return self.__track_item.measure_items()[self.index + 1]

    def topLeft(self) -> QtCore.QPoint:
        return self.__top_left

    def setTopLeft(self, pos: QtCore.QPoint) -> None:
        self.__top_left = QtCore.QPoint(pos)

    def scaleX(self) -> fractions.Fraction:
        return self.track_item.scaleX()

    def width(self) -> int:
        raise NotImplementedError

    def height(self) -> int:
        return self.track_item.height()

    def size(self) -> QtCore.QSize:
        return QtCore.QSize(self.width(), self.height())

    def rect(self) -> QtCore.QRect:
        return QtCore.QRect(0, 0, self.width(), self.height())

    def viewRect(self) -> QtCore.QRect:
        return QtCore.QRect(
            self.track_item.viewTopLeft() + self.topLeft(), self.size())

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

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        raise NotImplementedError

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        pass

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        pass


class MeasureEditorItem(selection_set.Selectable, BaseMeasureEditorItem):
    selection_class = 'measure'

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

        self.__selected = False
        self.__hovered = False

        self.measure_listeners = []  # type: List[core.Listener]

        if self.__measure is not None:
            self.addMeasureListeners()

        self.track_item.hoveredMeasureChanged.connect(self.__onHoveredMeasureChanged)

    def close(self) -> None:
        if self.selected():
            self.selection_set.remove(self, update_object=False)

        for listener in self.measure_listeners:
            listener.remove()
        self.measure_listeners.clear()

        self.track_item.hoveredMeasureChanged.disconnect(self.__onHoveredMeasureChanged)

        super().close()

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

    def __measureChanged(self, change: model.PropertyValueChange[music.Measure]) -> None:
        for listener in self.measure_listeners:
            listener.remove()
        self.measure_listeners.clear()

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
        self.send_command_async(music.Command(
            target=self.project.id,
            insert_measure=music.InsertMeasure(
                tracks=[self.track.id],
                pos=self.measure_reference.index)))

    def onRemoveMeasure(self) -> None:
        self.send_command_async(music.Command(
            target=self.project.id,
            remove_measure=music.RemoveMeasure(
                tracks=[self.track.index],
                pos=self.measure_reference.index)))

    def setSelected(self, selected: bool) -> None:
        if selected != self.__selected:
            self.__selected = selected
            self.rectChanged.emit(self.viewRect())

    def selected(self) -> bool:
        return self.__selected

    def __onHoveredMeasureChanged(self, measure_id: int) -> None:
        hovered = (measure_id == self.measure_reference.measure.id)
        if hovered != self.__hovered:
            self.__hovered = hovered
            self.rectChanged.emit(self.viewRect())

    def getCopy(self) -> Dict[str, Any]:
        return {
            'class': type(self.__measure).__name__,
            'id': self.__measure.id,
            'data': self.__measure.serialize(),
        }

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

        if self.__selected:
            painter.fillRect(paint_rect, QtGui.QColor(255, 200, 200))
        elif self.__hovered:
            painter.fillRect(paint_rect, QtGui.QColor(220, 220, 255))

        for layer in self.layers:
            if layer == self.PLAYBACK_POS:
                if self.playbackPos() is not None:
                    self.paintPlaybackPos(painter)
            else:
                painter.drawPixmap(0, 0, self.__paint_caches[layer])


class Appendix(BaseMeasureEditorItem):
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


class MeasuredToolBase(tools.ToolBase):  # pylint: disable=abstract-method
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__mouse_grabber = None  # type: BaseMeasureEditorItem
        self.__mouse_pos = None  # type: QtCore.QPoint

    def _measureItemUnderMouse(self, target: Any) -> BaseMeasureEditorItem:
        if self.__mouse_pos is None:
            return None
        return target.measureItemAt(self.__mouse_pos)

    def __makeMouseEvent(
            self, measure_item: BaseMeasureEditorItem, evt: QtGui.QMouseEvent
    ) -> QtGui.QMouseEvent:
        return QtGui.QMouseEvent(
            evt.type(),
            evt.localPos() - measure_item.topLeft(),
            evt.windowPos(),
            evt.screenPos(),
            evt.button(),
            evt.buttons(),
            evt.modifiers())

    def _mousePressEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        measure_item = target.measureItemAt(evt.pos())
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeMouseEvent(measure_item, evt)
            self.mousePressEvent(measure_item, measure_evt)
            if measure_evt.isAccepted():
                self.__mouse_grabber = measure_item
            evt.setAccepted(measure_evt.isAccepted())

        elif isinstance(measure_item, Appendix):
            if measure_item.clickRect().contains(evt.pos() - measure_item.topLeft()):
                self.send_command_async(music.Command(
                    target=target.project.id,
                    insert_measure=music.InsertMeasure(tracks=[], pos=-1)))
                evt.accept()
                return

    def _mouseReleaseEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        if isinstance(self.__mouse_grabber, MeasureEditorItem):
            measure_evt = self.__makeMouseEvent(self.__mouse_grabber, evt)
            self.mouseReleaseEvent(self.__mouse_grabber, measure_evt)
            self.__mouse_grabber = None
            evt.setAccepted(measure_evt.isAccepted())
            target.setHoverMeasureItem(target.measureItemAt(evt.pos()), evt)

    def _mouseMoveEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        if self.__mouse_grabber is not None:
            measure_item = self.__mouse_grabber
        else:
            measure_item = target.measureItemAt(evt.pos())
            target.setHoverMeasureItem(measure_item, evt)

        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeMouseEvent(measure_item, evt)
            self.mouseMoveEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

        elif isinstance(measure_item, Appendix):
            measure_item.setHover(
                measure_item.clickRect().contains(evt.pos() - measure_item.topLeft()))

    def _mouseDoubleClickEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        measure_item = target.measureItemAt(evt.pos())
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeMouseEvent(measure_item, evt)
            self.mouseDoubleClickEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def _wheelEvent(self, target: Any, evt: QtGui.QWheelEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        measure_item = target.measureItemAt(evt.pos())
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = QtGui.QWheelEvent(
                evt.pos() - measure_item.topLeft(),
                evt.globalPos(),
                evt.pixelDelta(),
                evt.angleDelta(),
                0,
                Qt.Horizontal,
                evt.buttons(),
                evt.modifiers(),
                evt.phase(),
                evt.source())
            self.wheelEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def __makeKeyEvent(
            self, measure_item: BaseMeasureEditorItem, evt: QtGui.QKeyEvent) -> QtGui.QKeyEvent:
        return QtGui.QKeyEvent(
            evt.type(),
            evt.key(),
            evt.modifiers(),
            evt.nativeScanCode(),
            evt.nativeVirtualKey(),
            evt.nativeModifiers(),
            evt.text(),
            evt.isAutoRepeat(),
            evt.count())

    def _keyPressEvent(self, target: Any, evt: QtGui.QKeyEvent) -> None:
        measure_item = self._measureItemUnderMouse(target)
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeKeyEvent(measure_item, evt)
            self.keyPressEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def _keyReleaseEvent(self, target: Any, evt: QtGui.QKeyEvent) -> None:
        measure_item = self._measureItemUnderMouse(target)
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeKeyEvent(measure_item, evt)
            self.keyReleaseEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())


class ArrangeMeasuresTool(tools.ToolBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.ARRANGE_MEASURES,
            group=tools.ToolGroup.ARRANGE,
            **kwargs)

        self.__selection_first = None  # type: MeasureEditorItem
        self.__selection_last = None  # type: MeasureEditorItem

    def iconName(self) -> str:
        return 'pointer'

    def mousePressEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        if evt.button() == Qt.LeftButton and evt.modifiers() == Qt.NoModifier:
            measure_item = target.measureItemAt(evt.pos())

            if isinstance(measure_item, MeasureEditorItem):
                self.selection_set.clear()

                self.selection_set.add(measure_item)
                self.__selection_first = measure_item
                self.__selection_last = None
                evt.accept()
                return

        # TODO: handle click on appendix
        super().mousePressEvent(target, evt)

    def mouseReleaseEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        if evt.button() == Qt.LeftButton:
            self.__selection_first = None
            self.__selection_last = None
            evt.accept()
            return

        super().mouseReleaseEvent(target, evt)

    def mouseMoveEvent(self, target: Any, evt: QtGui.QMouseEvent) -> None:
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__
        measure_item = target.measureItemAt(evt.pos())
        target.setHoverMeasureItem(measure_item, evt)

        if self.__selection_first is not None and isinstance(measure_item, MeasureEditorItem):
            start_idx = self.__selection_first.measure_reference.index
            last_idx = measure_item.measure_reference.index

            if start_idx > last_idx:
                start_idx, last_idx = last_idx, start_idx

            for mitem in itertools.islice(target.measure_items(), start_idx, last_idx + 1):
                if isinstance(mitem, MeasureEditorItem) and not mitem.selected():
                    self.selection_set.add(mitem)

            for sitem in list(self.selection_set):
                assert isinstance(sitem, MeasureEditorItem)
                if (not (start_idx <= sitem.measure_reference.index <= last_idx)
                        and sitem.selected()):
                    self.selection_set.remove(sitem)

            self.__selection_last = measure_item

            evt.accept()
            return

        super().mouseMoveEvent(target, evt)


class MeasuredTrackEditorItem(BaseTrackEditorItem):
    hoveredMeasureChanged = QtCore.pyqtSignal(int)

    measure_item_cls = None  # type: Type[MeasureEditorItem]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__closing = False
        self.__listeners = []  # type: List[core.Listener]
        self.__measure_item_at_playback_pos = None  # type: BaseMeasureEditorItem
        self.__hover_measure_item = None  # type: BaseMeasureEditorItem

        self.__measure_items = []  # type: List[BaseMeasureEditorItem]
        for idx, mref in enumerate(self.track.measure_list):
            self.addMeasure(idx, mref)

        appendix_item = Appendix(track_item=self, context=self.context)
        appendix_item.rectChanged.connect(self.rectChanged)
        self.__measure_items.append(appendix_item)

        self.__listeners.append(self.track.measure_list_changed.add(self.onMeasureListChanged))

        self.updateMeasures()

    def close(self) -> None:
        self.__closing = True

        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

        while len(self.__measure_items) > 0:
            self.removeMeasure(0)

        super().close()

    @property
    def track(self) -> music.MeasuredTrack:
        return down_cast(music.MeasuredTrack, super().track)

    def measure_items(self) -> List[BaseMeasureEditorItem]:
        return self.__measure_items

    def onMeasureListChanged(
            self, change: model.PropertyListChange[music.MeasureReference]) -> None:
        if isinstance(change, model.PropertyListInsert):
            self.addMeasure(change.index, change.new_value)

        elif isinstance(change, model.PropertyListDelete):
            self.removeMeasure(change.index)

        else:
            raise TypeError(type(change))

    def addMeasure(self, idx: int, mref: music.MeasureReference) -> None:
        measure_item = self.measure_item_cls(  # pylint: disable=not-callable
            track_item=self, measure_reference=mref, context=self.context)
        measure_item.rectChanged.connect(self.rectChanged)
        self.__measure_items.insert(idx, measure_item)
        self.updateMeasures()
        self.rectChanged.emit(self.viewRect())

    def removeMeasure(self, idx: int) -> None:
        measure_item = self.__measure_items.pop(idx)
        measure_item.close()
        measure_item.rectChanged.disconnect(self.rectChanged)
        self.updateMeasures()
        self.rectChanged.emit(self.viewRect())

    def updateMeasures(self) -> None:
        if self.__closing:
            return

        p = QtCore.QPoint(10, 0)
        for measure_item in self.measure_items():
            measure_item.setTopLeft(p)
            p += QtCore.QPoint(measure_item.width(), 0)

        self.setWidth(p.x() + 10)

    def setScaleX(self, scale_x: fractions.Fraction) -> None:
        super().setScaleX(scale_x)
        self.updateMeasures()

    def setPlaybackPos(self, time: audioproc.MusicalTime) -> None:
        if self.__measure_item_at_playback_pos is not None:
            self.__measure_item_at_playback_pos.clearPlaybackPos()
            self.__measure_item_at_playback_pos = None

        measure_time = audioproc.MusicalTime()
        for measure_item in self.measure_items():
            if measure_time <= time < measure_time + measure_item.duration:
                measure_item.setPlaybackPos(time - measure_time)
                self.__measure_item_at_playback_pos = measure_item
                break
            measure_time += measure_item.duration

    def measureItemAt(self, pos: QtCore.QPoint) -> BaseMeasureEditorItem:
        p = QtCore.QPoint(10, 0)
        for measure_item in self.measure_items():
            if p.x() <= pos.x() < p.x() + measure_item.width():
                return measure_item

            p += QtCore.QPoint(measure_item.width(), 0)

        return None

    def buildContextMenu(self, menu: QtWidgets.QMenu, pos: QtCore.QPoint) -> None:
        super().buildContextMenu(menu, pos)

        measure_item = self.measureItemAt(pos)
        if measure_item is not None:
            measure_item.buildContextMenu(
                menu, pos - measure_item.topLeft())

    def onInsertMeasure(self) -> None:
        self.send_command_async(music.Command(
            target=self.project.id,
            insert_measure=music.InsertMeasure(
                tracks=[self.track.id],
                pos=self.measure_reference.index)))

    def onRemoveMeasure(self) -> None:
        self.send_command_async(music.Command(
            target=self.project.id,
            remove_measure=music.RemoveMeasure(
                tracks=[self.track.index],
                pos=self.measure_reference.index)))

    def setHoverMeasureItem(
            self, measure_item: Optional[BaseMeasureEditorItem],
            evt: Union[None, QtGui.QEnterEvent, QtGui.QMouseEvent]
    ) -> None:
        if measure_item is self.__hover_measure_item:
            return

        if self.__hover_measure_item is not None:
            measure_evt = QtCore.QEvent(QtCore.QEvent.Leave)
            self.__hover_measure_item.leaveEvent(measure_evt)

        if measure_item is not None:
            measure_evt = QtGui.QEnterEvent(
                evt.localPos() - measure_item.topLeft(),
                evt.windowPos(),
                evt.screenPos())
            measure_item.enterEvent(measure_evt)

        self.__hover_measure_item = measure_item
        self.hoveredMeasureChanged.emit(
            measure_item.measure_reference.measure.id
            if self.isCurrent() and isinstance(measure_item, MeasureEditorItem)
            else 0)

    def enterEvent(self, evt: QtCore.QEvent) -> None:
        evt = down_cast(QtGui.QEnterEvent, evt)
        self.setHoverMeasureItem(self.measureItemAt(evt.pos()), evt)

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.setHoverMeasureItem(None, None)

    def purgePaintCaches(self) -> None:
        super().purgePaintCaches()
        for measure_item in self.measure_items():
            measure_item.purgePaintCaches()

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        super().paint(painter, paint_rect)

        p = QtCore.QPoint(10, 0)
        for measure_item in self.measure_items():
            measure_rect = QtCore.QRect(p.x(), 0, measure_item.width(), self.height())
            measure_rect = measure_rect.intersected(paint_rect)
            if not measure_rect.isEmpty():
                painter.save()
                try:
                    painter.setClipRect(measure_rect)
                    painter.translate(p)
                    measure_item.paint(painter, measure_rect.translated(-p))
                finally:
                    painter.restore()
            p += QtCore.QPoint(measure_item.width(), 0)
