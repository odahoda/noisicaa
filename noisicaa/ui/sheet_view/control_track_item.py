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

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui

from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import tools
from . import base_track_item

logger = logging.getLogger(__name__)


class ControlPoint(object):
    def __init__(self, track_item=None, point=None):
        self.__track_item = track_item
        self.__point = point

        self.__pos = QtCore.QPoint(
            self.__track_item.timeposToX(self.__point.timepos),
            self.__track_item.valueToY(self.__point.value))

        self.__listeners = [
            self.__point.listeners.add('timepos', self.onTimeposChanged),
            self.__point.listeners.add('value', self.onValueChanged),
        ]

    def close(self):
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

    def onTimeposChanged(self, old_timepos, new_timepos):
        self.__pos = QtCore.QPoint(
            self.__track_item.timeposToX(new_timepos),
            self.__pos.y())
        self.__track_item.rectChanged.emit(self.__track_item.sheetRect())

    def onValueChanged(self, old_value, new_value):
        self.__pos = QtCore.QPoint(
            self.__pos.x(),
            self.__track_item.valueToY(new_value))
        self.__track_item.rectChanged.emit(self.__track_item.sheetRect())

    @property
    def index(self):
        return self.__point.index

    @property
    def point_id(self):
        return self.__point.id

    @property
    def timepos(self):
        return self.__point.timepos

    def pos(self):
        return self.__pos

    def setPos(self, pos):
        if pos is None:
            self.__pos = QtCore.QPoint(
                self.__track_item.timeposToX(self.__point.timepos),
                self.__track_item.valueToY(self.__point.value))
        else:
            self.__pos = pos


class ControlTrackEditorItemImpl(base_track_item.BaseTrackEditorItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__mouse_pos = None
        self.__highlighted_point = None
        self.__moving_point = None
        self.__moving_point_original_pos = None
        self.__moving_point_offset = None
        self.__move_mode = 'any'
        self.__move_range = None

        self.__listeners = []
        self.__points = []

        for point in self.track.points:
            self.addPoint(len(self.__points), point)

        self.__listeners.append(self.track.listeners.add(
            'points', self.onPointsChanged))

        self.updateSize()

    def close(self):
        for points in self.__points:
            points.close()
        self.__points.clear()
        super().close()

    def supportedTools(self):
        return {
            tools.Tool.POINTER,
        }

    def defaultTool(self):
        return tools.Tool.POINTER

    def updateSize(self):
        width = 20
        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width += int(self.scaleX() * measure.duration)
        self.setSize(QtCore.QSize(width, 120))

    def setHighlightedPoint(self, cpoint):
        if cpoint is not self.__highlighted_point:
            self.__highlighted_point = cpoint
            self.rectChanged.emit(self.sheetRect())

    def updateHighlightedPoint(self):
        if self.__mouse_pos is None:
            self.setHighlightedPoint(None)
            return

        closest_cpoint = None
        closest_dist = None
        for cpoint in self.__points:
            dist = ((cpoint.pos().x() - self.__mouse_pos.x()) ** 2
                    + (cpoint.pos().y() - self.__mouse_pos.y()) ** 2)
            if dist < 20**2 and (closest_dist is None or dist < closest_dist):
                closest_dist = dist
                closest_cpoint = cpoint

        self.setHighlightedPoint(closest_cpoint)

    def setPointPos(self, cpoint, pos):
        cpoint.setPos(pos)
        self.rectChanged.emit(self.sheetRect())

    def addPoint(self, insert_index, point):
        cpoint = ControlPoint(track_item=self, point=point)
        self.__points.insert(insert_index, cpoint)
        self.rectChanged.emit(self.sheetRect())

    def removePoint(self, remove_index, point):
        cpoint = self.__points.pop(remove_index)
        cpoint.close()
        self.rectChanged.emit(self.sheetRect())

    def onPointsChanged(self, action, *args):
        if action == 'insert':
            insert_index, point = args
            self.addPoint(insert_index, point)
            self.updateHighlightedPoint()

        elif action == 'delete':
            remove_index, point = args
            self.removePoint(remove_index, point)
            self.updateHighlightedPoint()

        else:
            raise ValueError("Unknown action %r" % action)

    def valueToY(self, value):
        return int(self.height() - int(self.height() * value))

    def yToValue(self, y):
        return float(self.height() - y) / self.height()

    def timeposToX(self, timepos):
        x = 10
        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if timepos <= measure.duration:
                return x + int(width * timepos / measure.duration)

            x += width
            timepos -= measure.duration

        return x

    def xToTimepos(self, x):
        x -= 10
        timepos = music.Duration(0, 1)
        if x <= 0:
            return timepos

        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if x <= width:
                return music.Duration(timepos + measure.duration * music.Duration(int(x), width))

            timepos += measure.duration
            x -= width

        return music.Duration(timepos)

    def leaveEvent(self, evt):
        self.__mouse_pos = None
        self.setHighlightedPoint(None)
        super().leaveEvent(evt)

    def mousePressEvent(self, evt):
        self.__mouse_pos = evt.pos()
        self.updateHighlightedPoint()

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self.__highlighted_point is not None):
            self.__moving_point = self.__highlighted_point
            self.__moving_point_original_pos = self.__moving_point.pos()
            self.__moving_point_offset = evt.pos() - self.__moving_point.pos()
            self.__move_mode = 'any'

            point_index = self.__moving_point.index

            if point_index > 0:
                range_left = self.__points[point_index - 1].pos().x() + 1
            else:
                range_left = 10

            if point_index < len(self.__points) - 1:
                range_right = self.__points[point_index + 1].pos().x() - 1
            else:
                range_right = self.width() - 11

            self.__move_range = (range_left, range_right)

            evt.accept()
            return

        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier
                and self.__highlighted_point is not None):
            self.send_command_async(
                self.track.id,
                'RemoveControlPoint',
                point_id=self.__highlighted_point.point_id)

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__moving_point is not None:
            self.setPointPos(self.__moving_point, self.__moving_point_original_pos)
            self.__moving_point = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        self.__mouse_pos = evt.pos()

        if self.__moving_point is not None:
            new_pos = evt.pos() - self.__moving_point_offset

            if evt.modifiers() == Qt.ControlModifier:
                delta = new_pos - self.__moving_point_original_pos
                if self.__move_mode == 'any' and delta.manhattanLength() > 5:
                    if abs(delta.x()) > abs(delta.y()):
                        self.__move_mode = 'horizontal'
                    else:
                        self.__move_mode = 'vertical'
            else:
                self.__move_mode = 'any'

            if self.__move_mode == 'horizontal':
                new_pos.setY(self.__moving_point_original_pos.y())
            elif self.__move_mode == 'vertical':
                new_pos.setX(self.__moving_point_original_pos.x())

            range_left, range_right = self.__move_range
            if new_pos.x() < range_left:
                new_pos.setX(range_left)
            elif new_pos.x() > range_right:
                new_pos.setX(range_right)

            if new_pos.y() < 0:
                new_pos.setY(0)
            elif new_pos.y() > self.height() - 1:
                new_pos.setY(self.height() - 1)

            self.setPointPos(self.__moving_point, new_pos)

            evt.accept()
            return

        self.updateHighlightedPoint()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        self.__mouse_pos = evt.pos()
        if evt.button() == Qt.LeftButton and self.__moving_point is not None:
            pos = self.__moving_point.pos()
            self.__moving_point = None

            if self.__move_mode != 'vertical':
                new_timepos = self.xToTimepos(pos.x())
            else:
                new_timepos = None

            if self.__move_mode != 'horizontal':
                new_value = self.yToValue(pos.y())
            else:
                new_value = None

            self.send_command_async(
                self.track.id,
                'MoveControlPoint',
                point_id=self.__highlighted_point.point_id,
                timepos=new_timepos,
                value=new_value)

            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def mouseDoubleClickEvent(self, evt):
        self.__mouse_pos = evt.pos()
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier):
            # If the first half of the double click initiated a move,
            # cancel that move now.
            if self.__moving_point is not None:
                self.setPointPos(self.__moving_point, self.__moving_point_original_pos)
                self.__moving_point = None

            timepos = self.xToTimepos(evt.pos().x())
            for point in self.track.points:
                if point.timepos == timepos:
                    self.send_command_async(
                        self.track.id,
                        'MoveControlPoint',
                        point_id=point.id,
                        value=self.yToValue(evt.pos().y()))
                    break
            else:
                self.send_command_async(
                    self.track.id,
                    'AddControlPoint',
                    timepos=self.xToTimepos(evt.pos().x()),
                    value=self.yToValue(evt.pos().y()))

            evt.accept()
            return

        super().mouseDoubleClickEvent(evt)

    def paint(self, painter, paintRect):
        super().paint(painter, paintRect)

        x = 10
        timepos = music.Duration()
        for mref in self.sheet.property_track.measure_list:
            measure = mref.measure
            width = int(self.scaleX() * measure.duration)

            if x + width > paintRect.x() and x < paintRect.x() + paintRect.width():
                if mref.is_first:
                    painter.fillRect(x, 0, 2, self.height(), QtGui.QColor(160, 160, 160))
                else:
                    painter.fillRect(x, 0, 1, self.height(), QtGui.QColor(160, 160, 160))

                for i in range(1, measure.time_signature.upper):
                    pos = int(width * i / measure.time_signature.lower)
                    painter.fillRect(x + pos, 0, 1, self.height(), QtGui.QColor(200, 200, 200))

            x += width
            timepos += measure.duration

        painter.fillRect(x - 2, 0, 2, self.height(), QtGui.QColor(160, 160, 160))

        points = self.__points[:]

        px, py = None, None
        for cpoint in points:
            x = cpoint.pos().x()
            y = cpoint.pos().y()

            if px is not None:
                painter.setPen(Qt.black)
                painter.drawLine(px, py, x, y)

            px, py = x, y

        for cpoint in points:
            x = cpoint.pos().x()
            y = cpoint.pos().y()

            if cpoint is self.__highlighted_point:
                painter.setPen(Qt.black)
                painter.drawLine(x - 4, y - 4, x + 4, y - 4)
                painter.drawLine(x + 4, y - 4, x + 4, y + 4)
                painter.drawLine(x + 4, y + 4, x - 4, y + 4)
                painter.drawLine(x - 4, y + 4, x - 4, y - 4)
                painter.fillRect(x - 3, y - 3, 7, 7, QtGui.QColor(160, 160, 255))
            else:
                painter.setPen(Qt.black)
                painter.drawLine(x - 3, y - 3, x + 3, y - 3)
                painter.drawLine(x + 3, y - 3, x + 3, y + 3)
                painter.drawLine(x + 3, y + 3, x - 3, y + 3)
                painter.drawLine(x - 3, y + 3, x - 3, y - 3)


class ControlTrackEditorItem(ui_base.ProjectMixin, ControlTrackEditorItemImpl):
    pass
