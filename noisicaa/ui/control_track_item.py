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
    def __init__(self, parent=None, graph=None, point=None):
        super().__init__(parent=parent)

        self._graph = graph
        self._point = point

        self._listeners = [
            self._point.listeners.add('timepos', self.onTimeposChanged),
            self._point.listeners.add('value', self.onValueChanged),
        ]

        self.setRect(-3, -3, 6, 6)
        self.setPen(Qt.black)
        self.setBrush(QtGui.QBrush(Qt.NoBrush))

    def close(self):
        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    def onTimeposChanged(self, old_timepos, new_timepos):
        self._graph.setHandlePos(
            self,
            QtCore.QPointF(self._graph.timeposToX(new_timepos), self.pos().y()))

    def onValueChanged(self, old_value, new_value):
        self._graph.setHandlePos(
            self,
            QtCore.QPointF(self.pos().x(), self._graph.valueToY(new_value)))

    @property
    def index(self):
        return self._point.index

    @property
    def point_id(self):
        return self._point.id

    @property
    def timepos(self):
        return self._point.timepos

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setRect(-4, -4, 8, 8)
            self.setBrush(QtGui.QColor(200, 200, 255))
        else:
            self.setRect(-3, -3, 6, 6)
            self.setBrush(QtGui.QBrush(Qt.NoBrush))


class ControlGraph(ui_base.ProjectMixin, QGraphicsGroup):
    def __init__(self, track=None, size=None, widths=None, **kwargs):
        super().__init__(**kwargs)

        self._track = track
        self._size = size
        self._widths = widths

        self._listeners = []

        self._mouse_pos = None
        self._highlighted_handle = None
        self._moving_handle = None
        self._moving_handle_original_pos = None
        self._moving_handle_offset = None
        self._move_mode = 'any'
        self._move_range = None

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

        for point in self._track.points:
            self.addPoint(len(self._handles), point)

        self._listeners.append(self._track.listeners.add(
            'points', self.onPointsChanged))

    def close(self):
        for handle in self._handles:
            handle.close()
        self._handles.clear()

        self._segments.clear()

        for listener in self._listeners:
            listener.remove()
        self._listeners.clear()

    def valueToY(self, value):
        return int(self.height - int(self.height * value))

    def yToValue(self, y):
        return float(self.height - y) / self.height

    def timeposToX(self, timepos):
        return int(400 * timepos)

    def xToTimepos(self, x):
        return music.Duration(int(x), 400)

    @property
    def width(self):
        return self._size.width()

    @property
    def height(self):
        return self._size.height()

    def onPointsChanged(self, action, *args):
        if action == 'insert':
            insert_index, point = args
            self.addPoint(insert_index, point)
            self.updateHighlightedHandle()

        elif action == 'delete':
            remove_index, point = args
            self.removePoint(remove_index, point)
            self.updateHighlightedHandle()

        else:
            raise ValueError("Unknown action %r" % action)

    def addPoint(self, insert_index, point):
        if insert_index > 0:
            prev_handle = self._handles[insert_index - 1]
        else:
            prev_handle = None

        if insert_index < len(self._handles):
            next_handle = self._handles[insert_index]
        else:
            next_handle = None

        handle = Handle(parent=self, graph=self, point=point)
        handle.setPos(self.timeposToX(point.timepos), self.valueToY(point.value))
        self._handles.insert(insert_index, handle)

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

    def removePoint(self, remove_index, point):
        if remove_index > 0:
            prev_handle = self._handles[remove_index - 1]
        else:
            prev_handle = None

        if remove_index < len(self._handles) - 1:
            next_handle = self._handles[remove_index + 1]
        else:
            next_handle = None

        handle = self._handles.pop(remove_index)
        handle.close()
        handle.scene().removeItem(handle)

        if next_handle is not None:
            segment = self._segments.pop(remove_index)
            segment.scene().removeItem(segment)

            if prev_handle is not None:
                self._segments[remove_index - 1].setLine(QtCore.QLineF(
                    prev_handle.pos(), next_handle.pos()))
        elif prev_handle is not None:
            segment = self._segments.pop(remove_index - 1)
            segment.scene().removeItem(segment)

    def setHighlightedHandle(self, handle):
        if self._highlighted_handle is not None:
            self._highlighted_handle.setHighlighted(False)
            self._highlighted_handle = None

        if handle is not None:
            handle.setHighlighted(True)
            self._highlighted_handle = handle

    def updateHighlightedHandle(self):
        if self._mouse_pos is None:
            self.setHighlightedHandle(None)
            return

        closest_handle = None
        closest_dist = None
        for handle in self._handles:
            dist = ((handle.pos().x() - self._mouse_pos.x()) ** 2
                    + (handle.pos().y() - self._mouse_pos.y()) ** 2)
            if dist < 20**2 and (closest_dist is None or dist < closest_dist):
                closest_dist = dist
                closest_handle = handle

        self.setHighlightedHandle(closest_handle)

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
        self._mouse_pos = evt.pos()
        super().hoverLeaveEvent(evt)

    def hoverLeaveEvent(self, evt):
        self.ungrabMouse()
        self._mouse_pos = None
        self.setHighlightedHandle(None)
        super().hoverLeaveEvent(evt)

    def mousePressEvent(self, evt):
        self._mouse_pos = evt.pos()
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self._highlighted_handle is not None):
            self._moving_handle = self._highlighted_handle
            self._moving_handle_original_pos = self._moving_handle.pos()
            self._moving_handle_offset = evt.pos() - self._moving_handle.pos()
            self._move_mode = 'any'

            handle_index = self._moving_handle.index

            if handle_index > 0:
                range_left = self._handles[handle_index - 1].pos().x() + 1
            else:
                range_left = 0

            if handle_index < len(self._handles) - 1:
                range_right = self._handles[handle_index + 1].pos().x() - 1
            else:
                range_right = self.width

            self._move_range = (range_left, range_right)

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and self._highlighted_handle is not None):
            self.send_command_async(
                self._track.id,
                'RemoveControlPoint',
                point_id=self._highlighted_handle.point_id)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self._moving_handle is not None:
            self.setHandlePos(self._moving_handle, self._moving_handle_original_pos)
            self._moving_handle = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseDoubleClickEvent(self, evt):
        self._mouse_pos = evt.pos()
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            # If the first half of the double click initiated a move,
            # cancel that move now.
            if self._moving_handle is not None:
                self.setHandlePos(self._moving_handle, self._moving_handle_original_pos)
                self._moving_handle = None

            timepos = self.xToTimepos(evt.pos().x())
            for handle in self._handles:
                if handle.timepos == timepos:
                    self.send_command_async(
                        self._track.id,
                        'MoveControlPoint',
                        point_id=handle.point_id,
                        value=self.yToValue(evt.pos().y()))
                    break
            else:
                self.send_command_async(
                    self._track.id,
                    'AddControlPoint',
                    timepos=self.xToTimepos(evt.pos().x()),
                    value=self.yToValue(evt.pos().y()))

            evt.accept()
            return

        super().mouseDoubleClickEvent(evt)

    def mouseMoveEvent(self, evt):
        self._mouse_pos = evt.pos()
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

            range_left, range_right = self._move_range
            if new_pos.x() < range_left:
                new_pos.setX(range_left)
            elif new_pos.x() > range_right:
                new_pos.setX(range_right)

            if new_pos.y() < 0:
                new_pos.setY(0)
            elif new_pos.y() > self.height:
                new_pos.setY(self.height)

            self.setHandlePos(self._moving_handle, new_pos)

            evt.accept()
            return

        self.updateHighlightedHandle()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        self._mouse_pos = evt.pos()
        if evt.button() == Qt.LeftButton and self._moving_handle is not None:
            pos = self._moving_handle.pos()
            self._moving_handle = None

            if self._move_mode != 'vertical':
                new_timepos = self.xToTimepos(pos.x())
            else:
                new_timepos = None

            if self._move_mode != 'horizontal':
                new_value = self.yToValue(pos.y())
            else:
                new_value = None

            self.send_command_async(
                self._track.id,
                'MoveControlPoint',
                point_id=self._highlighted_handle.point_id,
                timepos=new_timepos,
                value=new_value)

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

        self._graph = None

    def close(self):
        super().close()

        if self._graph is not None:
            self._graph.close()
            self._graph = None

    def getLayout(self):
        return ControlTrackLayout(self._track)

    def renderTrack(self, y, track_layout):
        layer = self._sheet_view.layers[base_track_item.Layer.MAIN]

        text = QtWidgets.QGraphicsSimpleTextItem(layer)
        text.setText("> %s" % self._track.name)
        text.setPos(0, y)

        if self._graph is not None:
            self._graph.close()
            self._graph = None

        self._graph = ControlGraph(
            parent=layer,
            track=self._track,
            size=QtCore.QSize(sum(track_layout.widths[:-1]), track_layout.height - 20),
            widths=track_layout.widths[:-1],
            **self.context)
        self._graph.setPos(0, y + 20)


class ControlTrackItem(ui_base.ProjectMixin, ControlTrackItemImpl):
    pass
