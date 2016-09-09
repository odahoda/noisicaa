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
    def __init__(self, parent=None, graph=None, idx=None):
        super().__init__(parent=parent)

        self._graph = graph
        self._index = idx

        self.setRect(-3, -3, 6, 6)
        self.setPen(Qt.black)
        self.setBrush(QtGui.QBrush(Qt.NoBrush))

        self._moving = False
        self._move_handle_pos = None
        self._moved = False

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.grabMouse()
            self._moving = True
            self._move_handle_pos = evt.scenePos() - self.pos()
            self._moved = False
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        if self._moving:
            new_pos = evt.scenePos() - self._move_handle_pos

            if new_pos.x() < 0:
                new_pos.setX(0)
            elif new_pos.x() > self._graph.width:
                new_pos.setX(self._graph.width)

            if new_pos.y() < 0:
                new_pos.setY(0)
            elif new_pos.y() > self._graph.height:
                new_pos.setY(self._graph.height)

            self.setPos(new_pos)

            if self._index < len(self._graph.handles) - 1:
                segment = self._graph.segments[self._index]
                segment.setLine(QtCore.QLineF(new_pos, segment.line().p2()))

            if self._index > 0:
                segment = self._graph.segments[self._index - 1]
                segment.setLine(QtCore.QLineF(segment.line().p1(), new_pos))

            self._moved = True
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if evt.button() == Qt.LeftButton and self._moving:
            if self._moved:
                pass

            self.ungrabMouse()
            self._moving = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)


class ControlGraph(QGraphicsGroup):
    def __init__(self, parent=None, track=None, size=None, widths=None):
        super().__init__(parent=parent)

        self._track = track
        self._size = size
        self._widths = widths

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

        self.handles = []
        self.segments = []

        prev_x = 0
        prev_timepos = music.Duration(0, 4)
        prev_value = 0.0

        def _value_to_y(v):
            return int(self.height - int(self.height * v))

        for point in self._track.points:
            if point.timepos != prev_timepos:
                x = prev_x + 50

                if not self.handles:
                    handle = Handle(parent=self, graph=self, idx=len(self.handles))
                    handle.setPos(prev_x, _value_to_y(prev_value))
                    self.handles.append(handle)

                left_point = self.handles[-1].pos()
                right_point = QtCore.QPointF(x, _value_to_y(point.value))

                handle = Handle(parent=self, graph=self, idx=len(self.handles))
                handle.setPos(right_point)
                self.handles.append(handle)

                segment = QtWidgets.QGraphicsLineItem(self)
                segment.setLine(
                    prev_x, _value_to_y(prev_value),
                    x, _value_to_y(point.value))
                segment.setPen(Qt.black)
                self.segments.append(segment)

                prev_x = x
                prev_timepos = point.timepos
                prev_value = point.value

    @property
    def width(self):
        return self._size.width()

    @property
    def height(self):
        return self._size.height()


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
