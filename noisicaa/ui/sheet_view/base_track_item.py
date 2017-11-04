#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from fractions import Fraction
import logging
import enum
import time

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.ui import tools
from noisicaa.ui import ui_base
from noisicaa.ui import selection_set

logger = logging.getLogger(__name__)


class BaseTrackItem(QtCore.QObject):
    rectChanged = QtCore.pyqtSignal(QtCore.QRect)
    sizeChanged = QtCore.pyqtSignal(QtCore.QSize)

    def __init__(self, *, track, **kwargs):
        super().__init__(**kwargs)

        self.__track = track
        self.__scale_x = Fraction(500, 1)
        self.__sheet_top_left = QtCore.QPoint()
        self.__is_current = False

        self.__size = QtCore.QSize()

    def close(self):
        pass

    @property
    def track(self):
        return self.__track

    @property
    def sheet(self):
        return self.track.sheet

    def scaleX(self):
        return self.__scale_x

    def setScaleX(self, scale_x):
        self.__scale_x = scale_x
        self.updateSize()
        self.purgePaintCaches()
        self.rectChanged.emit(self.sheetRect())

    def width(self):
        return self.__size.width()

    def setWidth(self, width):
        self.setSize(QtCore.QSize(width, self.height()))

    def height(self):
        return self.__size.height()

    def setHeight(self, height):
        self.setSize(QtCore.QSize(self.width(), height))

    def size(self):
        return QtCore.QSize(self.__size)

    def setSize(self, size):
        if size != self.__size:
            self.__size = QtCore.QSize(size)
            self.sizeChanged.emit(self.__size)

    def updateSize(self):
        pass

    def sheetTopLeft(self):
        return self.__sheet_top_left

    def sheetLeft(self):
        return self.__sheet_top_left.x()

    def sheetTop(self):
        return self.__sheet_top_left.y()

    def setSheetTopLeft(self, top_left):
        self.__sheet_top_left = QtCore.QPoint(top_left)

    def sheetRect(self):
        return QtCore.QRect(self.__sheet_top_left, self.size())

    def isCurrent(self):
        return self.__is_current

    def buildContextMenu(self, menu, pos):
        remove_track_action = QtWidgets.QAction(
            "Remove track", menu,
            statusTip="Remove this track.",
            triggered=self.onRemoveTrack)
        menu.addAction(remove_track_action)

    def onRemoveTrack(self):
        self.send_command_async(
            self.sheet.id, 'RemoveTrack',
            track_id=self.track.id)

    def setIsCurrent(self, is_current):
        if is_current != self.__is_current:
            self.__is_current = is_current
            self.rectChanged.emit(self.sheetRect())

    def purgePaintCaches(self):
        pass

    def paint(self, painter, paintRect):
        if self.isCurrent():
            painter.fillRect(paintRect, QtGui.QColor(240, 240, 255))
        else:
            painter.fillRect(paintRect, Qt.white)

    def enterEvent(self, evt):
        pass

    def leaveEvent(self, evt):
        pass

    def mousePressEvent(self, evt):
        pass

    def mouseReleaseEvent(self, evt):
        pass

    def mouseDoubleClickEvent(self, evt):
        pass

    def mouseMoveEvent(self, evt):
        pass

    def wheelEvent(self, evt):
        pass

    def keyPressEvent(self, evt):
        pass

    def keyReleaseEvent(self, evt):
        pass


class BaseTrackEditorItem(BaseTrackItem):
    currentToolChanged = QtCore.pyqtSignal(tools.ToolType)

    toolBoxClass = None

    def __init__(self, *, player_state, sheet_view, **kwargs):
        super().__init__(**kwargs)

        self.__player_state = player_state
        self.__sheet_view = sheet_view

    def toolBox(self):
        tool_box = self.__sheet_view.currentToolBox()
        assert isinstance(tool_box, self.toolBoxClass)
        return tool_box

    def currentTool(self):
        return self.toolBox().currentTool()

    def currentToolType(self):
        return self.toolBox().currentToolType()

    def toolBoxMatches(self):
        return isinstance(self.__sheet_view.currentToolBox(), self.toolBoxClass)

    def playerState(self):
        return self.__player_state

    def setPlaybackPos(self, timepos):
        pass

    def mouseMoveEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().mouseMoveEvent(self, evt)

    def mousePressEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().mousePressEvent(self, evt)

    def mouseReleaseEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().mouseReleaseEvent(self, evt)

    def mouseDoubleClickEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().mouseDoubleClickEvent(self, evt)

    def wheelEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().wheelEvent(self, evt)

    def keyPressEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().keyPressEvent(self, evt)

    def keyReleaseEvent(self, evt):
        if self.toolBoxMatches():
            return self.toolBox().keyReleaseEvent(self, evt)


class BaseMeasureEditorItem(selection_set.Selectable, QtCore.QObject):
    selection_class = 'measure'

    rectChanged = QtCore.pyqtSignal(QtCore.QRect)

    def __init__(self, track_item, **kwargs):
        super().__init__(**kwargs)

        self.__top_left = QtCore.QPoint()
        self.__track_item = track_item

    def close(self):
        pass

    @property
    def track_item(self):
        return self.__track_item

    @property
    def track(self):
        return self.__track_item.track

    @property
    def sheet(self):
        return self.track.sheet

    def topLeft(self):
        return self.__top_left

    def setTopLeft(self, pos):
        self.__top_left = QtCore.QPoint(pos)

    def scaleX(self):
        return self.track_item.scaleX()

    def width(self):
        raise NotImplementedError

    def height(self):
        return self.track_item.height()

    def size(self):
        return QtCore.QSize(self.width(), self.height())

    def rect(self):
        return QtCore.QRect(0, 0, self.width(), self.height())

    def sheetRect(self):
        return QtCore.QRect(
            self.track_item.sheetTopLeft() + self.topLeft(), self.size())

    def buildContextMenu(self, menu, pos):
        pass

    def purgePaintCaches(self):
        pass

    def paint(self, painter, paintRect):
        raise NotImplementedError

    def enterEvent(self, evt):
        pass

    def leaveEvent(self, evt):
        pass


class MeasureEditorItem(BaseMeasureEditorItem):
    PLAYBACK_POS = 'playback_pos'

    def __init__(self, measure_reference, **kwargs):
        super().__init__(**kwargs)

        self.__paint_caches = {}
        self.__cached_size = QtCore.QSize()

        self.__measure_reference = measure_reference

        self.__measure = self.__measure_reference.measure
        self.__measure_listener = self.__measure_reference.listeners.add(
            'measure_id', self.__measureChanged)

        self.__playback_timepos = None

        self.__selected = False

        self.measure_listeners = []

        if self.__measure is not None:
            self.addMeasureListeners()

    def close(self):
        if self.selected():
            self.selection_set.remove(self, update_object=False)

        for listener in self.measure_listeners:
            listener.remove()
        self.measure_listeners.clear()

        super().close()

    @property
    def measure_reference(self):
        return self.__measure_reference

    @property
    def measure(self):
        return self.__measure

    @property
    def is_first(self):
        return (
            self.__measure_reference is not None
            and self.__measure_reference.index == 0)

    def width(self):
        return int(self.scaleX() * self.measure.duration)

    def addMeasureListeners(self):
        raise NotImplementedError

    def __measureChanged(self, old_value, new_value):
        for listener in self.measure_listeners:
            listener.remove()
        self.measure_listeners.clear()

        self.purgePaintCaches()

        self.__measure = self.__measure_reference.measure
        self.addMeasureListeners()

        self.rectChanged.emit(self.sheetRect())

    def buildContextMenu(self, menu, pos):
        super().buildContextMenu(menu, pos)

        insert_measure_action = QtWidgets.QAction(
            "Insert measure", menu,
            statusTip="Insert an empty measure at this point.",
            triggered=self.onInsertMeasure)
        menu.addAction(insert_measure_action)

        remove_measure_action = QtWidgets.QAction(
            "Remove measure", menu,
            statusTip="Remove this measure.",
            triggered=self.onRemoveMeasure)
        menu.addAction(remove_measure_action)

    def onInsertMeasure(self):
        self.send_command_async(
            self.sheet.id, 'InsertMeasure',
            tracks=[self.track.id],
            pos=self.measure_reference.index)

    def onRemoveMeasure(self):
        self.send_command_async(
            self.sheet.id, 'RemoveMeasure',
            tracks=[self.track.index],
            pos=self.measure_reference.index)

    def playbackPos(self):
        return self.__playback_timepos

    def clearPlaybackPos(self):
        self.__playback_timepos = None
        self.rectChanged.emit(self.sheetRect())

    def setPlaybackPos(self, timepos):
        self.__playback_timepos = timepos
        self.rectChanged.emit(self.sheetRect())

    def setSelected(self, selected):
        if selected != self.__selected:
            self.__selected = selected
            self.rectChanged.emit(self.sheetRect())

    def selected(self):
        return self.__selected

    async def getCopy(self):
        return {
            'class': type(self.__measure).__name__,
            'id': self.__measure.id,
            'data': await self.project_client.serialize(self.__measure.id),
        }

    def purgePaintCaches(self):
        self.__paint_caches.clear()

    def invalidatePaintCache(self, *layers):
        for layer in layers:
            self.__paint_caches.pop(layer, None)
        self.rectChanged.emit(self.sheetRect())

    def paintPlaybackPos(self, painter):
        raise NotImplementedError

    def paint(self, painter, paintRect):
        if self.__cached_size != self.size():
            self.__paint_caches.clear()

        for layer in self.layers:
            if layer == self.PLAYBACK_POS:
                continue
            if layer not in self.__paint_caches:
                pixmap = QtGui.QPixmap(self.size())
                pixmap.fill(Qt.transparent)
                layer_painter = QtGui.QPainter(pixmap)
                t1 = time.perf_counter()
                self.paintLayer(layer, layer_painter)
                t2 = time.perf_counter()
                layer_painter.end()
                # logger.info(
                #     "%s.paintLayer(%s): %.2fµs",
                #     type(self).__name__, layer, 1e6 * (t2 - t1))

                self.__paint_caches[layer] = pixmap

        self.__cached_size = self.size()

        if self.selected():
            painter.fillRect(paintRect, QtGui.QColor(255, 200, 200))

        for layer in self.layers:
            if layer == self.PLAYBACK_POS:
                if self.playbackPos() is not None:
                    self.paintPlaybackPos(painter)
            else:
                painter.drawPixmap(0, 0, self.__paint_caches[layer])


class Appendix(ui_base.ProjectMixin, BaseMeasureEditorItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__hover = False

    def setHover(self, hover):
        if hover != self.__hover:
            self.__hover = hover
            self.rectChanged.emit(self.sheetRect())

    def clickRect(self):
        ymid = self.height() // 2
        y1 = max(5, ymid - 40)
        y2 = min(self.height() - 5, ymid + 40)
        return QtCore.QRect(10, y1, 80, y2 - y1 + 1)

    def width(self):
        return 90

    def paint(self, painter, paintRect):
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

    def leaveEvent(self, evt):
        self.setHover(False)
        super().leaveEvent(evt)


class MeasuredToolBase(tools.ToolBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__mouse_grabber = None
        self.__mouse_pos = None

    def _measureItemUnderMouse(self, target):
        if self.__mouse_pos is None:
            return None
        return target.measureItemAt(self.__mouse_pos)

    def __makeMouseEvent(self, measure_item, evt):
        return QtGui.QMouseEvent(
            evt.type(),
            evt.localPos() - measure_item.topLeft(),
            evt.windowPos(),
            evt.screenPos(),
            evt.button(),
            evt.buttons(),
            evt.modifiers())

    def _mousePressEvent(self, target, evt):
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
                self.send_command_async(
                    target.sheet.id,
                    'InsertMeasure', tracks=[], pos=-1)
                evt.accept()
                return

    def _mouseReleaseEvent(self, target, evt):
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        if isinstance(self.__mouse_grabber, MeasureEditorItem):
            measure_evt = self.__makeMouseEvent(self.__mouse_grabber, evt)
            self.mouseReleaseEvent(self.__mouse_grabber, measure_evt)
            self.__mouse_grabber = None
            evt.setAccepted(measure_evt.isAccepted())
            target.setHoverMeasureItem(target.measureItemAt(evt.pos()), evt)

    def _mouseMoveEvent(self, target, evt):
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

    def _mouseDoubleClickEvent(self, target, evt):
        assert isinstance(target, MeasuredTrackEditorItem), type(target).__name__

        self.__mouse_pos = evt.pos()

        measure_item = target.measureItemAt(evt.pos())
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeMouseEvent(measure_item, evt)
            self.mouseDoubleClickEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def _wheelEvent(self, target, evt):
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

    def __makeKeyEvent(self, measure_item, evt):
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

    def _keyPressEvent(self, target, evt):
        measure_item = self._measureItemUnderMouse(target)
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeKeyEvent(measure_item, evt)
            self.keyPressEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())

    def _keyReleaseEvent(self, target, evt):
        measure_item = self._measureItemUnderMouse(target)
        if isinstance(measure_item, MeasureEditorItem):
            measure_evt = self.__makeKeyEvent(measure_item, evt)
            self.keyReleaseEvent(measure_item, measure_evt)
            evt.setAccepted(measure_evt.isAccepted())


class ArrangeMeasuresTool(MeasuredToolBase):
    def __init__(self, **kwargs):
        super().__init__(
            type=tools.ToolType.ARRANGE_MEASURES,
            group=tools.ToolGroup.ARRANGE,
            **kwargs)

    def iconName(self):
        return 'pointer'

    def mousePressEvent(self, target, evt):
        assert isinstance(target, MeasureEditorItem), type(target).__name__
        track_item = target.track_item

        if target.selected():
            track_item.selection_set.remove(target)
        else:
            track_item.selection_set.add(target)
        evt.accept()


class MeasuredTrackEditorItem(BaseTrackEditorItem):
    measure_item_cls = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__closing = False
        self.__listeners = []
        self.__measure_item_at_playback_pos = None
        self.__hover_measure_item = None

        self.__measure_items = []
        for idx, mref in enumerate(self.track.measure_list):
            self.addMeasure(idx, mref)

        appendix_item = Appendix(track_item=self, **self.context)
        appendix_item.rectChanged.connect(self.rectChanged)
        self.__measure_items.append(appendix_item)

        self.__listeners.append(self.track.listeners.add(
            'measure_list', self.onMeasureListChanged))

        self.updateMeasures()

    def close(self):
        self.__closing = True

        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

        while len(self.__measure_items) > 0:
            self.removeMeasure(0)

        super().close()

    def measure_items(self):
        return self.__measure_items

    def onMeasureListChanged(self, action, *args):
        if action == 'insert':
            idx, mref = args
            self.addMeasure(idx, mref)

        elif action == 'delete':
            idx, mref = args
            self.removeMeasure(idx)

        else:
            raise ValueError("Unknown action %r" % action)

    def addMeasure(self, idx, mref):
        measure_item = self.measure_item_cls(  # pylint: disable=not-callable
            track_item=self, measure_reference=mref, **self.context)
        measure_item.rectChanged.connect(self.rectChanged)
        self.__measure_items.insert(idx, measure_item)
        self.updateMeasures()
        self.rectChanged.emit(self.sheetRect())

    def removeMeasure(self, idx):
        measure_item = self.__measure_items.pop(idx)
        measure_item.close()
        measure_item.rectChanged.disconnect(self.rectChanged)
        self.updateMeasures()
        self.rectChanged.emit(self.sheetRect())

    def updateMeasures(self):
        if self.__closing:
            return

        p = QtCore.QPoint(10, 0)
        for measure_item in self.measure_items():
            measure_item.setTopLeft(p)
            p += QtCore.QPoint(measure_item.width(), 0)

        self.setWidth(p.x() + 10)

    def setScaleX(self, scale_x):
        super().setScaleX(scale_x)
        self.updateMeasures()

    def setPlaybackPos(self, timepos):
        if self.__measure_item_at_playback_pos is not None:
            self.__measure_item_at_playback_pos.clearPlaybackPos()
            self.__measure_item_at_playback_pos = None

        measure_timepos = music.Duration()
        for measure_item in self.measure_items():
            measure = measure_item.measure
            if measure_timepos <= timepos < measure_timepos + measure.duration:
                measure_item.setPlaybackPos(timepos - measure_timepos)
                self.__measure_item_at_playback_pos = measure_item
                break
            measure_timepos += measure.duration

    def measureItemAt(self, pos):
        p = QtCore.QPoint(10, 0)
        for measure_item in self.measure_items():
            if p.x() <= pos.x() < p.x() + measure_item.width():
                return measure_item

            p += QtCore.QPoint(measure_item.width(), 0)

        return None

    def buildContextMenu(self, menu, pos):
        super().buildContextMenu(menu, pos)

        measure_item = self.measureItemAt(pos)
        if measure_item is not None:
            measure_item.buildContextMenu(
                menu, pos - measure_item.topLeft())

    def onInsertMeasure(self):
        self.send_command_async(
            self.sheet.id, 'InsertMeasure',
            tracks=[self.track.id],
            pos=self.measure_reference.index)

    def onRemoveMeasure(self):
        self.send_command_async(
            self.sheet.id, 'RemoveMeasure',
            tracks=[self.track.index],
            pos=self.measure_reference.index)

    def setHoverMeasureItem(self, measure_item, evt):
        if measure_item is self.__hover_measure_item:
            return

        if self.__hover_measure_item is not None:
            measure_evt = QtCore.QEvent(
                QtCore.QEvent.Leave)
            self.__hover_measure_item.leaveEvent(measure_evt)

        if measure_item is not None:
            measure_evt = QtGui.QEnterEvent(
                evt.localPos() - measure_item.topLeft(),
                evt.windowPos(),
                evt.screenPos())
            measure_item.enterEvent(measure_evt)

        self.__hover_measure_item = measure_item

    def enterEvent(self, evt):
        self.setHoverMeasureItem(self.measureItemAt(evt.pos()), evt)

    def leaveEvent(self, evt):
        self.setHoverMeasureItem(None, evt)

    def purgePaintCaches(self):
        super().purgePaintCaches()
        for measure_item in self.measure_items():
            measure_item.purgePaintCaches()

    def paint(self, painter, paintRect):
        super().paint(painter, paintRect)

        p = QtCore.QPoint(10, 0)
        for measure_item in self.measure_items():
            measure_rect = QtCore.QRect(p.x(), 0, measure_item.width(), self.height())
            measure_rect = measure_rect.intersected(paintRect)
            if not measure_rect.isEmpty():
                painter.save()
                try:
                    painter.setClipRect(measure_rect)
                    painter.translate(p)
                    measure_item.paint(painter, measure_rect.translated(-p))
                finally:
                    painter.restore()
            p += QtCore.QPoint(measure_item.width(), 0)
