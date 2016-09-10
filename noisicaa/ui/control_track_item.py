#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.music import model
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item
from . import layout

logger = logging.getLogger(__name__)


class Handle(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent=None, idx=None):
        super().__init__(parent=parent)

        self.index = idx

        self.setRect(-3, -3, 6, 6)
        self.setPen(Qt.black)
        self.setBrush(QtGui.QBrush(Qt.NoBrush))

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setRect(-4, -4, 8, 8)
            self.setBrush(QtGui.QColor(200, 200, 255))
        else:
            self.setRect(-3, -3, 6, 6)
            self.setBrush(QtGui.QBrush(Qt.NoBrush))


class ControlGraph(QGraphicsGroup):
    def __init__(self, parent=None, track=None, size=None, widths=None):
        super().__init__(parent=parent)

        self._track = track
        self._size = size
        self._widths = widths

        self._highlighted_handle = None
        self._moving_handle = None
        self._moving_handle_original_pos = None
        self._moving_handle_offset = None
        self._move_mode = 'any'

        self._handles = []
        self._segments = []

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.ArrowCursor)

        x = 0
        for width in self._widths:
            x += width

            l = QtWidgets.QGraphicsLineItem(self)
            l.setLine(x, 0, x, self.height)
            l.setPen(QtGui.QColor(240, 240, 240))

        frame = QtWidgets.QGraphicsRectItem(self)
        frame.setRect(0, 0, self.width, self.height)
        frame.setPen(QtGui.QColor(200, 200, 200))
        frame.setBrush(QtGui.QBrush(Qt.NoBrush))

        prev_x = 0
        prev_timepos = music.Duration(0, 4)
        prev_value = 0.0

        for point in self._track.points:
            if point.timepos != prev_timepos:
                x = prev_x + 50

                if not self._handles:
                    handle = Handle(parent=self, idx=len(self._handles))
                    handle.setPos(prev_x, self.valueToY(prev_value))
                    self._handles.append(handle)

                left_point = self._handles[-1].pos()
                right_point = QtCore.QPointF(x, self.valueToY(point.value))

                handle = Handle(parent=self, idx=len(self._handles))
                handle.setPos(right_point)
                self._handles.append(handle)

                segment = QtWidgets.QGraphicsLineItem(self)
                segment.setLine(
                    prev_x, self.valueToY(prev_value),
                    x, self.valueToY(point.value))
                segment.setPen(Qt.black)
                self._segments.append(segment)

                prev_x = x
                prev_timepos = point.timepos
                prev_value = point.value

    def valueToY(self, v):
        return int(self.height - int(self.height * v))

    def yToValue(self, y):
        return float(self.height - y) / self.height

    @property
    def width(self):
        return self._size.width()

    @property
    def height(self):
        return self._size.height()

    def setHighlightedHandle(self, handle):
        if self._highlighted_handle is not None:
            self._highlighted_handle.setHighlighted(False)
            self._highlighted_handle = None

        if handle is not None:
            handle.setHighlighted(True)
            self._highlighted_handle = handle

    def setHandlePos(self, handle, pos):
        handle.setPos(pos)

        if handle.index < len(self._handles) - 1:
            segment = self._segments[handle.index]
            segment.setLine(QtCore.QLineF(pos, segment.line().p2()))

        if handle.index > 0:
            segment = self._segments[handle.index - 1]
            segment.setLine(QtCore.QLineF(segment.line().p1(), pos))

    def hoverEnterEvent(self, evt):
        self.grabMouse()
        super().hoverLeaveEvent(evt)

    def hoverLeaveEvent(self, evt):
        self.ungrabMouse()
        self.setHighlightedHandle(None)
        super().hoverLeaveEvent(evt)

    def mousePressEvent(self, evt):
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self._highlighted_handle is not None):
            self._moving_handle = self._highlighted_handle
            self._moving_handle_original_pos = self._moving_handle.pos()
            self._moving_handle_offset = evt.pos() - self._moving_handle.pos()
            self._move_mode = 'any'

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and self._highlighted_handle is not None):
            remove_index = self._highlighted_handle.index
            self.setHighlightedHandle(None)

            if remove_index > 0:
                prev_handle = self._handles[remove_index - 1]
            else:
                prev_handle = None

            if remove_index < len(self._handles) - 1:
                next_handle = self._handles[remove_index + 1]
            else:
                next_handle = None

            handle = self._handles.pop(remove_index)
            handle.scene().removeItem(handle)

            for h in self._handles[remove_index:]:
                h.index -= 1

            if next_handle is not None:
                segment = self._segments.pop(remove_index)
                segment.scene().removeItem(segment)

                if prev_handle is not None:
                    self._segments[remove_index - 1].setLine(QtCore.QLineF(
                        prev_handle.pos(), next_handle.pos()))
            elif prev_handle is not None:
                segment = self._segments.pop(remove_index - 1)
                segment.scene().removeItem(segment)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self._moving_handle is not None:
            self.setHandlePos(self._moving_handle, self._moving_handle_original_pos)
            self._moving_handle = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseDoubleClickEvent(self, evt):
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            if self._moving_handle is not None:
                self.setHandlePos(self._moving_handle, self._moving_handle_original_pos)
                self._moving_handle = None

            for insert_index, handle in enumerate(self._handles):
                if handle.pos().x() >= evt.pos().x():
                    break
            else:
                insert_index = len(self._handles)

            if insert_index > 0:
                prev_handle = self._handles[insert_index - 1]
            else:
                prev_handle = None

            if insert_index < len(self._handles):
                next_handle = self._handles[insert_index]
            else:
                next_handle = None

            handle = Handle(parent=self, idx=insert_index)
            handle.setPos(evt.pos())
            self._handles.insert(insert_index, handle)
            for h in self._handles[insert_index + 1:]:
                h.index += 1

            if prev_handle is not None:
                segment = QtWidgets.QGraphicsLineItem(self)
                segment.setLine(QtCore.QLineF(prev_handle.pos(), handle.pos()))
                segment.setPen(Qt.black)
                self._segments.insert(insert_index - 1, segment)

            if next_handle is not None:
                if prev_handle is None:
                    segment = QtWidgets.QGraphicsLineItem(self)
                    segment.setLine(QtCore.QLineF(handle.pos(), next_handle.pos()))
                    segment.setPen(Qt.black)
                    self._segments.insert(insert_index, segment)
                else:
                    self._segments[insert_index].setLine(
                        QtCore.QLineF(handle.pos(), next_handle.pos()))

            self.setHighlightedHandle(handle)

            evt.accept()
            return

        super().mouseDoubleClickEvent(evt)

    def mouseMoveEvent(self, evt):
        if self._moving_handle is not None:
            new_pos = evt.pos() - self._moving_handle_offset

            if evt.modifiers() == Qt.ControlModifier:
                delta = new_pos - self._moving_handle_original_pos
                if self._move_mode == 'any' and delta.manhattanLength() > 5:
                    if abs(delta.x()) > abs(delta.y()):
                        self._move_mode = 'horizontal'
                    else:
                        self._move_mode = 'vertical'
            else:
                self._move_mode = 'any'

            if self._move_mode == 'horizontal':
                new_pos.setY(self._moving_handle_original_pos.y())
            elif self._move_mode == 'vertical':
                new_pos.setX(self._moving_handle_original_pos.x())

            if new_pos.x() < 0:
                new_pos.setX(0)
            elif new_pos.x() > self.width:
                new_pos.setX(self.width)

            if new_pos.y() < 0:
                new_pos.setY(0)
            elif new_pos.y() > self.height:
                new_pos.setY(self.height)

            self.setHandlePos(self._moving_handle, new_pos)

            evt.accept()
            return

        closest_handle = None
        closest_dist = None
        for handle in self._handles:
            dist = ((handle.pos().x() - evt.pos().x()) ** 2
                    + (handle.pos().y() - evt.pos().y()) ** 2)
            if dist < 20**2 and (closest_dist is None or dist < closest_dist):
                closest_dist = dist
                closest_handle = handle

        self.setHighlightedHandle(closest_handle)

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if evt.button() == Qt.LeftButton and self._moving_handle is not None:
            self._moving_handle = None
            evt.accept()
            return

        super().mouseReleaseEvent(evt)


class ControlTrackLayout(layout.TrackLayout):
    def __init__(self, track):
        super().__init__()
        self._track = track

    def list_points(self):
        num_measures = max(
            len(track.measure_list) for track in self._track.sheet.all_tracks
            if isinstance(track, model.MeasuredTrack))
        for pos in range(num_measures):
            yield (pos, 100)

    def set_widths(self, widths):
        super().set_widths(widths)

    @property
    def widths(self):
        return [width for _, width in self._widths]

    @property
    def width(self):
        return sum(self.widths)

    @property
    def height(self):
        return 120


class ControlTrackItemImpl(base_track_item.TrackItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def getLayout(self):
        return ControlTrackLayout(self._track)

    def renderTrack(self, y, track_layout):
        layer = self._sheet_view.layers[base_track_item.Layer.MAIN]

        text = QtWidgets.QGraphicsSimpleTextItem(layer)
        text.setText("> %s" % self._track.name)
        text.setPos(0, y)

        self._graph = ControlGraph(
            parent=layer,
            track=self._track,
            size=QtCore.QSize(sum(track_layout.widths[:-1]), track_layout.height - 20),
            widths=track_layout.widths[:-1])
        self._graph.setPos(0, y + 20)


class ControlTrackItem(ui_base.ProjectMixin, ControlTrackItemImpl):
    pass
