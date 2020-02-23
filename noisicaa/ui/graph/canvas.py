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

import logging
import os.path
from typing import cast, Any, Optional, Iterator, Callable, Type, List, Dict, Set

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants
from noisicaa import value_types
from noisicaa import music
from noisicaa import node_db
from noisicaa.ui import ui_base
from noisicaa.ui import slots
from noisicaa.builtin_nodes import ui_registry
from . import base_node
from . import generic_node
from . import plugin_node
from . import toolbox

logger = logging.getLogger(__name__)


node_cls_map = {
    'builtin://no-ui': base_node.Node,
    'builtin://generic': generic_node.GenericNode,
    'builtin://plugin': plugin_node.PluginNode,
}  # type: Dict[str, Type[base_node.Node]]

node_cls_map.update(ui_registry.node_ui_cls_map)


# Something is odd with the QWidgetAction class. The usual way to use the
# ProjectMixin doesn't work here.
class SelectNodeAction(QtWidgets.QWidgetAction, ui_base.ProjectMixin):
    nodeSelected = QtCore.pyqtSignal(str)

    def __init__(self, parent: QtCore.QObject, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)  # type: ignore[call-arg]

        self.setDefaultWidget(SelectNodeWidget(
            parent=parent, action=self, context=self.context))


class NodeFilter(QtWidgets.QLineEdit):
    def __init__(self, node_list: QtWidgets.QListWidget, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.__node_list = node_list

        self.addAction(
            QtGui.QIcon(os.path.join(constants.DATA_DIR, 'icons', 'edit-find.svg')),
            QtWidgets.QLineEdit.LeadingPosition)

        clear_action = QtWidgets.QAction("Clear search string", self)
        clear_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'edit-clear.svg')))
        clear_action.triggered.connect(self.clear)
        self.addAction(clear_action, QtWidgets.QLineEdit.TrailingPosition)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key_Up:
            for idx in range(self.__node_list.currentRow() - 1, -1, -1):
                item = self.__node_list.item(idx)
                if not item.isHidden():
                    self.__node_list.setCurrentRow(idx)
                    break

            event.accept()
            return

        if event.key() == Qt.Key_Down:
            for idx in range(self.__node_list.currentRow() + 1, self.__node_list.count()):
                item = self.__node_list.item(idx)
                if not item.isHidden():
                    self.__node_list.setCurrentRow(idx)
                    break

            event.accept()
            return

        super().keyPressEvent(event)


class SelectNodeWidget(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, *, action: SelectNodeAction, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__action = action

        self.__list = QtWidgets.QListWidget(self)
        self.__list.currentRowChanged.connect(self.__currentRowChanged)
        self.__list.itemDoubleClicked.connect(self.__itemDoubleClicked)

        for uri, node_desc in self.app.node_db.nodes:
            if node_desc.internal:
                continue
            list_item = QtWidgets.QListWidgetItem()
            list_item.setText(node_desc.display_name)
            list_item.setData(Qt.UserRole, uri)

            if node_desc.WhichOneof('icon') == 'builtin_icon':
                list_item.setIcon(QtGui.QIcon(os.path.join(
                    constants.DATA_DIR, 'icons', '%s.svg' % node_desc.builtin_icon)))

            self.__list.addItem(list_item)

        self.__filter = NodeFilter(self.__list, self)
        self.__filter.textChanged.connect(self.__nodeFilterChanged)
        self.__filter.returnPressed.connect(self.__nodeFilterSelect)

        self.__info_box = QtWidgets.QWidget(self)
        self.__info_box.setMinimumWidth(400)

        self.__info_name = QtWidgets.QLabel(self)
        font = QtGui.QFont(self.__info_name.font())
        font.setPointSizeF(1.4 * font.pointSizeF())
        font.setBold(True)
        self.__info_name.setFont(font)

        self.__info_uri = QtWidgets.QLabel(self)

        l3 = QtWidgets.QVBoxLayout()
        l3.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        l3.setSpacing(2)
        l3.addWidget(self.__info_name)
        l3.addWidget(self.__info_uri)
        l3.addStretch(1)
        self.__info_box.setLayout(l3)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        l1.setSpacing(0)
        l1.addWidget(self.__filter)
        l1.addWidget(self.__list, 1)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        l2.setSpacing(0)
        l2.addLayout(l1, 1)
        l2.addSpacing(4)
        l2.addWidget(self.__info_box, 2)

        self.setLayout(l2)

    def __nodeFilterChanged(self, text: str) -> None:
        first_visible = None
        for idx in range(self.__list.count()):
            item = self.__list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
                if first_visible is None:
                    first_visible = item
            else:
                item.setHidden(True)

        if self.__list.currentItem() is None or self.__list.currentItem().isHidden():
            self.__list.setCurrentItem(first_visible)

    def __itemDoubleClicked(self, item: QtWidgets.QListWidgetItem) -> None:
        self.__action.nodeSelected.emit(item.data(Qt.UserRole))
        #self.__action.trigger()
        self.__action.triggered.emit()

    def __currentRowChanged(self, row: int) -> None:
        item = self.__list.item(row)
        if item is not None:
            uri = item.data(Qt.UserRole)
            node_desc = self.app.node_db.get_node_description(uri)
            self.__info_name.setText(node_desc.display_name)
            self.__info_uri.setText(node_desc.uri)
        else:
            self.__info_name.setText("")
            self.__info_uri.setText("")

    def __nodeFilterSelect(self) -> None:
        item = self.__list.currentItem()
        if item is None:
            return

        self.__action.nodeSelected.emit(item.data(Qt.UserRole))
        self.__action.trigger()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.__filter.setFocus()


class DraggedConnection(QtWidgets.QGraphicsPathItem):
    def __init__(self, src_pos: QtCore.QPointF, swap: bool) -> None:
        super().__init__()

        pen = QtGui.QPen()
        pen.setColor(Qt.red)
        pen.setWidth(4)
        self.setPen(pen)

        self.__src_pos = src_pos
        self.__dest_pos = src_pos
        self.__swap = swap

        self.__layout()

    def setSrcPos(self, pos: QtCore.QPointF) -> None:
        self.__src_pos = pos
        self.__layout()

    def setDestPos(self, pos: QtCore.QPointF) -> None:
        self.__dest_pos = pos
        self.__layout()

    def __layout(self) -> None:
        pos1 = self.__src_pos
        pos2 = self.__dest_pos
        if self.__swap:
            pos1, pos2 = pos2, pos1
        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        self.setPath(path)


class Scene(slots.SlotContainer, ui_base.ProjectMixin, QtWidgets.QGraphicsScene):
    currentTrack, setCurrentTrack, currentTrackChanged = slots.slot(
        music.Track, 'currentTrack', allow_none=True)

    contentRect, setContentRect, contentRectChanged = slots.slot(
        QtCore.QRectF, 'contentRect')

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__zoom = 1.0
        self.__canvas_transform = QtGui.QTransform()
        self.__canvas_transform.scale(self.__zoom, self.__zoom)
        self.__canvas_inv_transform, _ = self.__canvas_transform.inverted()

        self.__highlighted_port = None  # type: base_node.Port
        self.__highlighted_connection = None  # type: base_node.Connection

        self.__nodes = []  # type: List[base_node.Node]
        self.__node_map = {}  # type: Dict[int, base_node.Node]

        self.__connections = []  # type: List[base_node.Connection]
        self.__connection_map = {}  # type: Dict[int, base_node.Connection]

        for index, node in enumerate(self.project.nodes):
            self.__addNode(node, index)
        for index, connection in enumerate(self.project.node_connections):
            self.__addConnection(connection, index)

        self.__nodes_listener = self.project.nodes_changed.add(
            self.__nodesChange)
        self.__nodeh_connections_listener = (
            self.project.node_connections_changed.add(
                self.__nodeConnectionsChange))

        self.__updateContentRect()
        self.__layoutContent()

    def __nodesChange(
            self, change: music.PropertyListChange[music.BaseNode]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addNode(change.new_value, change.index)

        elif isinstance(change, music.PropertyListDelete):
            self.__removeNode(change.old_value, change.index)

        elif isinstance(change, music.PropertyListMove):
            item = self.__nodes.pop(change.old_index)
            self.__nodes.insert(change.new_index, item)

        else:  # pragma: no cover
            raise TypeError(type(change))

        self.__updateContentRect()
        self.__layoutContent()

    def __addNode(self, node: music.BaseNode, index: int) -> base_node.Node:
        node_cls = node_cls_map[node.description.node_ui.type]
        item = node_cls(node=node, context=self.context)
        item.props.contentRectChanged.connect(lambda _: self.__updateContentRect())
        self.addItem(item)
        self.__nodes.insert(index, item)
        self.__node_map[node.id] = item
        item.setup()
        return item

    def __removeNode(self, node: music.BaseNode, index: int) -> None:
        item = self.__nodes[index]
        item.cleanup()
        del self.__nodes[index]
        del self.__node_map[node.id]
        self.removeItem(item)

    def __nodeConnectionsChange(
            self, change: music.PropertyListChange[music.NodeConnection]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__addConnection(change.new_value, change.index)

        elif isinstance(change, music.PropertyListDelete):
            self.__removeConnection(change.old_value, change.index)

        else:  # pragma: no cover
            raise TypeError(type(change))

    def __addConnection(
            self, connection: music.NodeConnection, index: int) -> base_node.Connection:
        item = base_node.Connection(
            connection=connection,
            src_node=self.__node_map[connection.source_node.id],
            dest_node=self.__node_map[connection.dest_node.id],
            context=self.context)
        self.addItem(item)
        self.__connections.insert(index, item)
        self.__connection_map[connection.id] = item
        return item

    def __removeConnection(
            self, connection: music.NodeConnection, index: int) -> None:
        item = self.__connections[index]
        item.cleanup()
        del self.__connections[index]
        del self.__connection_map[connection.id]
        self.removeItem(item)

    def connections(self) -> Iterator[base_node.Connection]:
        yield from self.__connections

    def nodes(self) -> Iterator[base_node.Node]:
        yield from self.__nodes

    def nodeAt(self, pos: QtCore.QPointF) -> Optional[base_node.Node]:
        for item in self.items(pos):
            while item is not None:
                if isinstance(item, base_node.Port):
                    break
                if isinstance(item, base_node.Node):
                    return item
                item = item.parentItem()
        return None

    def disableHighlights(self) -> None:
        self.setHighlightedPort(None)
        self.setHighlightedConnection(None)

    def highlightedPort(self) -> Optional[base_node.Port]:
        return self.__highlighted_port

    def setHighlightedPort(self, port: base_node.Port) -> None:
        if port is self.__highlighted_port:
            return

        if self.__highlighted_port is not None:
            self.__highlighted_port.setHighlighted(False)

        self.__highlighted_port = port

        if self.__highlighted_port is not None:
            self.__highlighted_port.setHighlighted(True)

    def highlightedConnection(self) -> Optional[base_node.Connection]:
        return self.__highlighted_connection

    def setHighlightedConnection(self, connection: base_node.Connection) -> None:
        if connection is self.__highlighted_connection:
            return

        if self.__highlighted_connection is not None:
            self.__highlighted_connection.setHighlighted(False)

        self.__highlighted_connection = connection

        if self.__highlighted_connection is not None:
            self.__highlighted_connection.setHighlighted(True)

    def zoom(self) -> float:
        return self.__zoom

    def setZoom(self, zoom: float) -> None:
        self.__zoom = zoom
        self.__updateTransform()
        self.__layoutContent()
        self.__updateContentRect()

    def resetView(self) -> None:
        self.__zoom = 1.0
        self.__updateTransform()
        self.__layoutContent()
        self.__updateContentRect()

    def __updateTransform(self) -> None:
        self.__canvas_transform = QtGui.QTransform()
        self.__canvas_transform.scale(self.__zoom, self.__zoom)
        self.__canvas_inv_transform, _ = self.__canvas_transform.inverted()

    def contentToScenePoint(self, point: QtCore.QPointF) -> QtCore.QPointF:
        return self.__canvas_transform.map(point)

    def contentToSceneRect(self, rect: QtCore.QRectF) -> QtCore.QRectF:
        return self.__canvas_transform.mapRect(rect)

    def sceneToContentPoint(self, point: QtCore.QPointF) -> QtCore.QPointF:
        return self.__canvas_inv_transform.map(point)

    def sceneToContentRect(self, rect: QtCore.QRectF) -> QtCore.QRectF:
        return self.__canvas_inv_transform.mapRect(rect)

    def __layoutContent(self) -> None:
        for node in self.__nodes:
            node.setCanvasTransform(self.__canvas_transform)

    def __updateContentRect(self) -> None:
        content_rect = QtCore.QRectF()
        for node in self.__nodes:
            content_rect |= node.contentRect()

        size = max(content_rect.width(), content_rect.height())
        if size < 1000:
            m = (1000 - size) / 2
            content_rect = content_rect.marginsAdded(QtCore.QMarginsF(m, m, m, m))

        self.setContentRect(content_rect)

    def connectPorts(self, port1: base_node.Port, port2: base_node.Port) -> None:
        if port1.direction() == node_db.PortDescription.OUTPUT:
            src_port = port1
            dest_port = port2
        else:
            src_port = port2
            dest_port = port1

        src_node = src_port.node()
        dest_node = dest_port.node()

        assert src_port.direction() == node_db.PortDescription.OUTPUT
        assert dest_port.direction() == node_db.PortDescription.INPUT

        already_exists = any(
            (conn.source_node.id == src_node.id()
             and conn.source_port == src_port.name()
             and conn.dest_node.id == dest_node.id()
             and conn.dest_port == dest_port.name())
            for conn in self.project.node_connections)

        if not already_exists:
            with self.project.apply_mutations(
                    'Connect nodes "%s" and "%s"' % (src_node.node().name, dest_node.node().name)):
                self.project.create_node_connection(
                    source_node=src_node.node(),
                    source_port=src_port.name(),
                    dest_node=dest_node.node(),
                    dest_port=dest_port.name())

    def selectAllNodes(self) -> None:
        for node in self.__nodes:
            node.setSelected(True)

    def deselectAllNodes(self) -> None:
        for node in self.__nodes:
            node.setSelected(False)

    def insertNode(self, uri: str, pos: QtCore.QPointF) -> None:
        node_desc = self.project.get_node_description(uri)
        with self.project.apply_mutations('Create node "%s"' % node_desc.display_name):
            self.project.create_node(
                uri,
                graph_pos=value_types.Pos2F(pos.x(), pos.y()),
                graph_size=value_types.SizeF(200, 100),
                graph_color=value_types.Color(0.8, 0.8, 0.8))


class Zoom(object):
    def __init__(self, direction: int, center: QtCore.QPointF) -> None:
        self.direction = direction
        self.center = center


class MiniMap(slots.SlotContainer, QtWidgets.QWidget):
    contentRect, setContentRect, contentRectChanged = slots.slot(
        QtCore.QRectF, 'contentRect')
    visibleCanvasRect, setVisibleCanvasRect, visibleCanvasRectChanged = slots.slot(
        QtCore.QRectF, 'visibleCanvasRect')
    centerChanged = QtCore.pyqtSignal(QtCore.QPointF)
    zoomStarted = QtCore.pyqtSignal(Zoom)

    def __init__(self, *, scene: Scene, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__scene = scene

        self.contentRectChanged.connect(lambda _: self.__updateTransform())
        self.visibleCanvasRectChanged.connect(lambda _: self.update())

        self.__map_transform = None  # type: QtGui.QTransform
        self.__opacity = 1.0
        self.__hover = False
        self.__dragging = False

        self.__visibility_timer = QtCore.QTimer(self)
        self.__visibility_timer.setTimerType(Qt.PreciseTimer)
        self.__visibility_timer.setInterval(1000 // 25)
        self.__visibility_timer.timeout.connect(self.__updateVisibility)
        self.__visibility_timer.start()

    def __updateVisibility(self) -> None:
        if self.__map_transform is None or self.visibleCanvasRect() is None:
            return

        visible_rect = self.__scene.sceneToContentRect(self.visibleCanvasRect())
        map_rect = self.__map_transform.inverted()[0].mapRect(
            QtCore.QRectF(0, 0, self.width() - 12, self.height() - 12))
        should_show_map = not visible_rect.contains(map_rect)

        if should_show_map or self.__hover or self.__dragging:
            if self.__opacity < 1.0:
                self.__opacity = min(self.__opacity + 0.2, 1.0)
                self.update()

        else:
            if self.__opacity > 0.0:
                self.__opacity = max(self.__opacity - 0.06, 0.0)
                self.update()

        self.setVisible(self.__opacity > 0.01)

    def __updateTransform(self) -> None:
        w, h = self.width(), self.height()
        content_rect = self.contentRect()

        self.__map_transform = QtGui.QTransform()
        self.__map_transform.translate(6, 6)

        h_scale = (w - 12) / content_rect.width()
        v_scale = (h - 12) / content_rect.height()
        scale = min(1.0, h_scale, v_scale)
        self.__map_transform.scale(scale, scale)

        map_rect = self.__map_transform.inverted()[0].mapRect(
            QtCore.QRectF(0, 0, w - 12, h - 12))
        if h_scale < v_scale:
            self.__map_transform.translate(
                -content_rect.left(),
                -content_rect.top() - (content_rect.height() - map_rect.height()) / 2)
        else:
            self.__map_transform.translate(
                -content_rect.left() - (content_rect.width() - map_rect.width()) / 2,
                -content_rect.top())

        self.update()

    def enterEvent(self, event: QtCore.QEvent) -> None:
        self.__hover = True
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self.__hover = False
        super().leaveEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        self.__updateTransform()
        super().resizeEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self.__dragging = True
            canvas_center = self.__map_transform.inverted()[0].map(event.pos())
            scene_center = self.__scene.contentToScenePoint(canvas_center)
            self.centerChanged.emit(scene_center)
            event.accept()
            return

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.__dragging:
            canvas_center = self.__map_transform.inverted()[0].map(event.pos())
            scene_center = self.__scene.contentToScenePoint(canvas_center)
            self.centerChanged.emit(scene_center)
            event.accept()
            return

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.__dragging and event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self.__dragging = False
            event.accept()
            return

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        self.zoomStarted.emit(Zoom(
            1 if event.angleDelta().y() > 0 else -1,
            self.__map_transform.inverted()[0].map(event.pos())))
        event.accept()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        w, h = self.width(), self.height()

        painter = QtGui.QPainter(self)
        try:
            painter.setOpacity(self.__opacity)

            painter.fillRect(2, 2, w - 4, h - 4, QtGui.QColor(240, 240, 240, 240))

            if self.__map_transform is not None:
                painter.setPen(QtGui.QColor(100, 100, 100, 100))
                for conn in self.__scene.connections():
                    painter.drawLine(
                        self.__map_transform.mapRect(conn.src_node().contentRect()).center(),
                        self.__map_transform.mapRect(conn.dest_node().contentRect()).center())

                node_color = QtGui.QColor(50, 50, 50)
                for node in self.__scene.nodes():
                    painter.fillRect(self.__map_transform.mapRect(node.contentRect()), node_color)

                v_rect = self.__map_transform.mapRect(
                    self.__scene.sceneToContentRect(self.visibleCanvasRect()))
                painter.fillRect(v_rect, QtGui.QColor(150, 150, 255, 200))

            frame_color = QtGui.QColor(100, 100, 100)
            painter.fillRect(0, 0, w, 2, frame_color)
            painter.fillRect(0, h - 2, w, 2, frame_color)
            painter.fillRect(0, 0, 2, h, frame_color)
            painter.fillRect(w - 2, 0, 2, h, frame_color)

        finally:
            painter.end()



ViewChange = cast(QtCore.QEvent.Type, QtCore.QEvent.registerEventType())


class ViewChangeEvent(QtCore.QEvent):
    def __init__(self) -> None:
        super().__init__(ViewChange)


class State(object):
    view_follows_mouse = False
    swallow_events = {
        QtCore.QEvent.ContextMenu,
        QtCore.QEvent.MouseButtonDblClick,
    }

    def __init__(self, *, event_handler: Callable[[QtCore.QEvent], None]) -> None:
        self.__event_handler = event_handler

    def handleEvent(self, event: QtCore.QEvent) -> None:
        if event.type() in self.swallow_events:
            event.accept()
            return

        self.__event_handler(event)


class DragCanvas(State):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.last_pos = None  # type: QtCore.QPointF


class DragNodes(State):
    view_follows_mouse = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.nodes = None  # type: Set[base_node.Node]
        self.last_pos = None  # type: QtCore.QPointF


class ResizeNode(State):
    view_follows_mouse = True

    def __init__(self, node: base_node.Node, side: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.side = side
        self.node = node
        self.last_pos = None  # type: QtCore.QPointF


class NewConnection(State):
    view_follows_mouse = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.connection = None  # type: DraggedConnection
        self.src_port = None  # type: base_node.Port
        self.dest_port = None  # type: base_node.Port


class ChangeConnection(State):
    view_follows_mouse = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.orig_connection = None  # type: base_node.Connection
        self.click_pos = None  # type: QtCore.QPointF
        self.connection = None  # type: DraggedConnection
        self.src_port = None  # type: base_node.Port
        self.dest_port = None  # type: base_node.Port


class Canvas(ui_base.ProjectMixin, slots.SlotContainer, QtWidgets.QGraphicsView):
    currentTrack, setCurrentTrack, currentTrackChanged = slots.slot(
        music.Track, 'currentTrack', allow_none=True)

    visibleCanvasRect, setVisibleCanvasRect, visibleCanvasRectChanged = slots.slot(
        QtCore.QRectF, 'visibleCanvasRect')

    zoomStarted = QtCore.pyqtSignal(Zoom)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setMouseTracking(True)
        self.setRenderHints(
            QtGui.QPainter.Antialiasing
            | QtGui.QPainter.SmoothPixmapTransform
            | QtGui.QPainter.HighQualityAntialiasing)  # type: ignore[arg-type]
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setSceneRect(-100000, -100000, 200000, 200000)

        self.rubberBandChanged.connect(self.__rubberBandChanged)

        self.currentTrackChanged.connect(self.__currentTrackChanged)
        self.zoomStarted.connect(self.__zoomStarted)

        self.__scene = Scene(context=self.context)
        self.setScene(self.__scene)

        self.__mouse_pos = QtCore.QPoint()
        self.__rubber_band_active = False
        self.__rubber_band_prev_selection = None  # type: Set[base_node.Node]

        self.__current_state = None  # type: State

        self.__zoom_dir = 0.0
        self.__zoom_point = None  # type: QtCore.QPointF
        self.__zoom_steps = 0

        self.__update_timer = QtCore.QTimer(self)
        self.__update_timer.setTimerType(Qt.PreciseTimer)
        self.__update_timer.setInterval(1000 // 50)
        self.__update_timer.timeout.connect(self.__updateCanvas)

        self.__select_all_action = QtWidgets.QAction("Select all nodes")
        self.__select_all_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'edit-select-all.svg')))
        self.__select_all_action.triggered.connect(self.__scene.selectAllNodes)

        self.__mini_map = MiniMap(scene=self.__scene, parent=self)
        self.__mini_map.setContentRect(self.__scene.contentRect())
        self.__scene.contentRectChanged.connect(self.__mini_map.setContentRect)
        self.visibleCanvasRectChanged.connect(self.__mini_map.setVisibleCanvasRect)
        self.__mini_map.centerChanged.connect(self.setCenter)
        self.__mini_map.zoomStarted.connect(self.zoomStarted)

    def __currentTrackChanged(self, track: music.Track) -> None:
        # TODO: select and show the node
        pass

    def __zoomStarted(self, zoom: Zoom) -> None:
        self.__zoom_point = zoom.center
        if zoom.direction > 0:
            self.__zoom_dir = 1.2
            self.__zoom_steps = 4
        else:
            self.__zoom_dir = 1 / 1.2
            self.__zoom_steps = 4

    def toolChanged(self, tool: toolbox.Tool) -> None:
        logger.info("Current tool: %s", tool)

    def resetView(self) -> None:
        self.setCenter(QtCore.QPointF())
        self.__scene.resetView()

    def setCenter(self, center: QtCore.QPointF) -> None:
        self.setOffset(center - QtCore.QPointF(self.width() / 2, self.height() / 2))

    def offset(self) -> QtCore.QPointF:
        return QtCore.QPointF(
            self.horizontalScrollBar().value(),
            self.verticalScrollBar().value())

    def setOffset(self, offset: QtCore.QPointF) -> None:
        self.horizontalScrollBar().setValue(int(offset.x()))
        self.verticalScrollBar().setValue(int(offset.y()))

        self.setVisibleCanvasRect(
            QtCore.QRectF(self.viewport().rect()).translated(self.offset()))

    def moveOffset(self, offset: QtCore.QPointF) -> None:
        self.setOffset(QtCore.QPointF(
            self.horizontalScrollBar().value() + int(offset.x()),
            self.verticalScrollBar().value() + int(offset.y())))

    def __rubberBandChanged(
            self, rect: QtCore.QRectF, begin: QtCore.QPointF, end: QtCore.QPointF) -> None:
        if rect.isValid():
            if not self.__rubber_band_active:
                logger.info("rubber start")
                self.__rubber_band_active = True
                self.__rubber_band_prev_selection = {
                    node for node in self.__scene.nodes() if node.selected()
                }
                self.__scene.disableHighlights()

            canvas_rect = self.viewportTransform().inverted()[0].mapRect(QtCore.QRectF(rect))
            for node in self.__scene.nodes():
                node.setSelected(
                    node in self.__rubber_band_prev_selection
                    or canvas_rect.intersects(node.canvasRect()))

        elif self.__rubber_band_active:
            logger.info("rubber end")
            self.__rubber_band_active = False
            self.__rubber_band_prev_selection = None

    def __updateCanvas(self) -> None:
        view_changed = False

        if self.__zoom_steps > 0:
            self.__zoom_steps -= 1

            p_center = self.__scene.contentToScenePoint(self.__zoom_point)
            self.__scene.setZoom(max(0.05, min(self.__scene.zoom() * self.__zoom_dir, 5.0)))

            p_new = self.__scene.contentToScenePoint(self.__zoom_point)
            self.moveOffset(p_new - p_center)

            view_changed = True

        elif (self.__rubber_band_active
              or (self.__current_state is not None and self.__current_state.view_follows_mouse)):
            dx, dy = 0.0, 0.0
            if self.__mouse_pos.x() < 50:
                dx = -min(100, 0.3 * (50 - self.__mouse_pos.x()))
            elif self.__mouse_pos.x() > self.viewport().width() - 50:
                dx = min(100, 0.3 * (self.__mouse_pos.x() - self.viewport().width() + 50))

            if self.__mouse_pos.y() < 50:
                dy = -min(100, 0.3 * (50 - self.__mouse_pos.y()))
            elif self.__mouse_pos.y() > self.viewport().height() - 50:
                dy = min(100, 0.3 * (self.__mouse_pos.y() - self.viewport().height() + 50))

            if dx != 0 or dy != 0:
                self.moveOffset(QtCore.QPointF(dx, dy))
                view_changed = True

        if view_changed and self.__current_state is not None:
            self.__current_state.handleEvent(ViewChangeEvent())

    def senseRect(self, pos: QtCore.QPointF, size: int) -> QtCore.QRectF:
        return QtCore.QRectF(pos.x() - size, pos.y() - size, 2 * size, 2 * size)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        self.__mini_map.resize(
            max(50, min(int(0.2 * self.width()), 200)),
            max(50, min(int(0.2 * self.height()), 150)))
        self.__mini_map.move(10, self.height() - self.__mini_map.height() - 10)
        super().resizeEvent(event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.__update_timer.start()
        self.setVisibleCanvasRect(
            QtCore.QRectF(self.viewport().rect()).translated(self.offset()))
        super().showEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        self.__update_timer.stop()
        self.__scene.disableHighlights()
        super().hideEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self.__scene.disableHighlights()
        super().leaveEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        if self.__current_state is not None:
            self.__current_state.handleEvent(event)
            if event.isAccepted():
                return

        menu = QtWidgets.QMenu(self)

        scene_pos = self.mapToScene(event.pos())
        click_node = self.__scene.nodeAt(scene_pos)
        if click_node is not None:
            click_node.buildContextMenu(menu)

        else:
            insert_node_menu = menu.addMenu("Insert nodes...")
            insert_node_action = SelectNodeAction(parent=self, context=self.context)
            # For some reason the menu does not close when the WidgetAction's triggered
            # signal fires.
            insert_node_action.nodeSelected.connect(lambda _: menu.close())
            insert_node_action.nodeSelected.connect(
                lambda uri: self.__scene.insertNode(uri, scene_pos))
            insert_node_menu.addAction(insert_node_action)

            menu.addSeparator()

            menu.addAction(self.__select_all_action)

        if not menu.isEmpty():
            menu.popup(event.globalPos())
            event.accept()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.__current_state is not None:
            self.__current_state.handleEvent(event)
            if event.isAccepted():
                return

        click_node = self.__scene.nodeAt(self.mapToScene(event.pos()))

        if (event.button() == Qt.LeftButton
                and click_node is not None
                and isinstance(click_node.node(), music.Track)):
            self.setCurrentTrack(cast(music.Track, click_node.node()))

        if (event.button() == Qt.LeftButton
                and event.modifiers() == Qt.NoModifier
                and (click_node is None or not click_node.selected())):
            self.__scene.deselectAllNodes()

        if (event.button() == Qt.LeftButton
                and event.modifiers() == Qt.ControlModifier
                and click_node is not None):
            click_node.setSelected(not click_node.selected())
            return

        if (event.button() == Qt.LeftButton
                and click_node is not None):
            side = click_node.resizeSide(self.mapToScene(event.pos()))
            if side is not None:
                self.__current_state = ResizeNode(
                    node=click_node, side=side, event_handler=self.resizeNodeEvent)
                self.__current_state.handleEvent(event)
                return

            if click_node.dragRect().translated(click_node.canvasTopLeft()).contains(
                    self.mapToScene(event.pos())):
                self.__current_state = DragNodes(event_handler=self.dragNodesEvent)
                self.__current_state.handleEvent(event)
                return

        if (event.button() == Qt.LeftButton
                and self.__scene.highlightedPort() is not None):
            self.__current_state = NewConnection(event_handler=self.newConnectionEvent)
            self.__current_state.handleEvent(event)
            return

        if (event.button() == Qt.LeftButton
                and self.__scene.highlightedConnection() is not None):
            self.__current_state = ChangeConnection(event_handler=self.changeConnectionEvent)
            self.__current_state.handleEvent(event)
            return

        if (event.button() == Qt.MiddleButton
                and click_node is None):
            self.__current_state = DragCanvas(event_handler=self.dragCanvasEvent)
            self.__current_state.handleEvent(event)
            return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.__current_state is not None:
            self.__current_state.handleEvent(event)
            if event.isAccepted():
                return

        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.__current_state is not None:
            self.__current_state.handleEvent(event)
            if event.isAccepted():
                return

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = event.pos()

        if self.__current_state is not None:
            self.__current_state.handleEvent(event)
            if event.isAccepted():
                return

        hover_node = self.__scene.nodeAt(self.mapToScene(event.pos()))

        # if hover_node is not None:
        #     side = hover_node.resizeSide(self.mapToScene(event.pos()))
        #     shape_map = {
        #         'top':         Qt.SizeVerCursor,
        #         'bottom':      Qt.SizeVerCursor,
        #         'left':        Qt.SizeHorCursor,
        #         'right':       Qt.SizeHorCursor,
        #         'topleft':     Qt.SizeFDiagCursor,
        #         'topright':    Qt.SizeBDiagCursor,
        #         'bottomleft':  Qt.SizeBDiagCursor,
        #         'bottomright': Qt.SizeFDiagCursor,
        #     }
        #     shape = shape_map.get(side, None)
        #     logger.error("%s %s %s", hover_node.name(), side, shape)
        #     if shape is not None:
        #         shape = Qt.CrossCursor
        #         if shape != self.cursor().shape():
        #             self.setCursor(QtGui.QCursor(shape))
        #     else:
        #         self.unsetCursor()

        # else:
        #     self.unsetCursor()

        if not self.__rubber_band_active and hover_node is None:
            port = None  # type: base_node.Port
            min_dist = None  # type: float
            for item in self.__scene.items(self.senseRect(self.mapToScene(event.pos()), 16)):
                if isinstance(item, base_node.Port):
                    deltaF = item.scenePos() - self.mapToScene(event.pos())
                    dist = QtCore.QPointF.dotProduct(deltaF, deltaF)
                    if min_dist is None or dist < min_dist:
                        port = item
                        min_dist = dist

            if port is not None:
                self.__scene.setHighlightedPort(port)
                self.__scene.setHighlightedConnection(None)
            else:
                connection = None
                for item in self.__scene.items(self.senseRect(self.mapToScene(event.pos()), 4)):
                    if isinstance(item, base_node.Connection):
                        if connection is None:
                            connection = item

                self.__scene.setHighlightedConnection(connection)
                self.__scene.setHighlightedPort(None)

        else:
            self.__scene.disableHighlights()

        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self.__current_state is not None:
            self.__current_state.handleEvent(event)
            if event.isAccepted():
                return

        self.zoomStarted.emit(Zoom(
            1 if event.angleDelta().y() > 0 else -1,
            self.__scene.sceneToContentPoint(self.mapToScene(event.pos()))))

    # Sadly pylint is confused by the use of __current_state in all the methods below.
    # pylint: disable=attribute-defined-outside-init
    def dragCanvasEvent(self, event: QtCore.QEvent) -> None:
        state = cast(DragCanvas, self.__current_state)

        if event.type() == QtCore.QEvent.MouseButtonPress:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.MiddleButton:
                state.last_pos = self.mapToScene(mevent.pos())
                self.__scene.disableHighlights()
                event.accept()
                return

        if event.type() == QtCore.QEvent.MouseMove:
            mevent = cast(QtGui.QMouseEvent, event)

            self.moveOffset(state.last_pos - self.mapToScene(mevent.pos()))
            state.last_pos = self.mapToScene(mevent.pos())
            event.accept()
            return

        if event.type() == QtCore.QEvent.MouseButtonRelease:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.MiddleButton:
                self.__current_state = None
                event.accept()
                return

    def dragNodesEvent(self, event: QtCore.QEvent) -> None:
        state = cast(DragNodes, self.__current_state)

        if event.type() == QtCore.QEvent.MouseButtonPress:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                click_node = self.__scene.nodeAt(self.mapToScene(mevent.pos()))
                assert click_node is not None
                state.nodes = {click_node} | {n for n in self.__scene.nodes() if n.selected()}
                state.last_pos = self.mapToScene(mevent.pos())
                self.__scene.disableHighlights()
                event.accept()
                return

        if event.type() in (QtCore.QEvent.MouseMove, ViewChange):
            if event.type() == QtCore.QEvent.MouseMove:
                mpos = cast(QtGui.QMouseEvent, event).pos()
            else:
                mpos = self.__mouse_pos

            delta = self.mapToScene(mpos) - state.last_pos
            for node in state.nodes:
                node.setCanvasTopLeft(node.canvasTopLeft() + delta)
            state.last_pos = self.mapToScene(mpos)
            event.accept()
            return

        if event.type() == QtCore.QEvent.MouseButtonRelease:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                with self.project.apply_mutations(
                        'Move node%s' % ('s' if len(state.nodes) != 1 else '')):
                    for node in state.nodes:
                        content_pos = self.__scene.sceneToContentPoint(node.canvasTopLeft())
                        new_graph_pos = value_types.Pos2F(content_pos.x(), content_pos.y())
                        if new_graph_pos != node.graph_pos():
                            node.node().graph_pos = new_graph_pos

                self.__current_state = None
                event.accept()
                return

    def resizeNodeEvent(self, event: QtCore.QEvent) -> None:
        state = cast(ResizeNode, self.__current_state)

        if event.type() == QtCore.QEvent.MouseButtonPress:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                state.last_pos = self.mapToScene(mevent.pos())
                self.__scene.disableHighlights()
                event.accept()
                return

        if event.type() in (QtCore.QEvent.MouseMove, ViewChange):
            if event.type() == QtCore.QEvent.MouseMove:
                mpos = cast(QtGui.QMouseEvent, event).pos()
            else:
                mpos = self.__mouse_pos

            delta = self.mapToScene(mpos) - state.last_pos
            rect = state.node.canvasRect()
            if state.side == 'top':
                rect.setTop(min(rect.bottom() - 20, rect.top() + delta.y()))
            elif state.side == 'bottom':
                rect.setBottom(max(rect.top() + 20, rect.bottom() + delta.y()))
            elif state.side == 'left':
                rect.setLeft(min(rect.right() - 20, rect.left() + delta.x()))
            elif state.side == 'right':
                rect.setRight(max(rect.left() + 20, rect.right() + delta.x()))
            elif state.side == 'topleft':
                rect.setTop(min(rect.bottom() - 20, rect.top() + delta.y()))
                rect.setLeft(min(rect.right() - 20, rect.left() + delta.x()))
            elif state.side == 'topright':
                rect.setTop(min(rect.bottom() - 20, rect.top() + delta.y()))
                rect.setRight(max(rect.left() + 20, rect.right() + delta.x()))
            elif state.side == 'bottomleft':
                rect.setBottom(max(rect.top() + 20, rect.bottom() + delta.y()))
                rect.setLeft(min(rect.right() - 20, rect.left() + delta.x()))
            elif state.side == 'bottomright':
                rect.setBottom(max(rect.top() + 20, rect.bottom() + delta.y()))
                rect.setRight(max(rect.left() + 20, rect.right() + delta.x()))
            else:
                raise AssertionError(state.side)

            state.node.setCanvasRect(rect)
            state.last_pos = self.mapToScene(mpos)
            event.accept()
            return

        if event.type() == QtCore.QEvent.MouseButtonRelease:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                content_rect = self.__scene.sceneToContentRect(state.node.canvasRect())
                new_graph_pos = value_types.Pos2F(content_rect.x(), content_rect.y())
                new_graph_size = value_types.SizeF(content_rect.width(), content_rect.height())
                if (new_graph_pos != state.node.graph_pos()
                        or new_graph_size != state.node.graph_size()):
                    with self.project.apply_mutations('%s: Resize node' % state.node.node().name):
                        state.node.node().graph_pos = new_graph_pos
                        state.node.node().graph_size = new_graph_size

                self.__current_state = None
                event.accept()
                return

    def __startConnectionDrag(self, port: base_node.Port) -> None:
        for target_node in self.__scene.nodes():
            for target_port in target_node.ports():
                if not port.canConnectTo(target_port):
                    continue

                target_port.setTargetType(port.preferredConnectionType(target_port))

    def __endConnectionDrag(self) -> None:
        for target_node in self.__scene.nodes():
            for target_port in target_node.ports():
                target_port.clearTargetType()

    def newConnectionEvent(self, event: QtCore.QEvent) -> None:
        state = cast(NewConnection, self.__current_state)

        if event.type() == QtCore.QEvent.MouseButtonPress:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                port = self.__scene.highlightedPort()
                state.connection = DraggedConnection(
                    port.handleScenePos(),
                    port.direction() == node_db.PortDescription.INPUT)
                self.__scene.addItem(state.connection)
                state.src_port = port
                self.__startConnectionDrag(port)
                self.__scene.disableHighlights()
                event.accept()
                return

        if event.type() in (QtCore.QEvent.MouseMove, ViewChange):
            if event.type() == QtCore.QEvent.MouseMove:
                mpos = cast(QtGui.QMouseEvent, event).pos()
            else:
                mpos = self.__mouse_pos

            dest_port = None  # type: base_node.Port
            min_dist = None  # type: float
            for item in self.__scene.items(self.senseRect(self.mapToScene(mpos), 32)):
                if not isinstance(item, base_node.Port):
                    continue
                if not state.src_port.canConnectTo(item):
                    continue

                delta = item.scenePos() - self.mapToScene(mpos)
                dist = QtCore.QPointF.dotProduct(delta, delta)
                if min_dist is None or dist < min_dist:
                    dest_port = item
                    min_dist = dist

            self.__scene.setHighlightedPort(dest_port)

            state.connection.setSrcPos(state.src_port.handleScenePos())
            if dest_port is not None:
                state.dest_port = dest_port
                state.connection.setDestPos(dest_port.handleScenePos())
            else:
                state.dest_port = None
                state.connection.setDestPos(self.mapToScene(mpos))
            event.accept()
            return

        if event.type() == QtCore.QEvent.MouseButtonRelease:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                if state.dest_port is not None:
                    self.__scene.connectPorts(state.src_port, state.dest_port)

                self.__scene.removeItem(state.connection)
                self.__endConnectionDrag()
                self.__current_state = None
                event.accept()
                return

            if mevent.button() == Qt.RightButton:
                # abort drag
                self.__scene.removeItem(state.connection)
                self.__endConnectionDrag()
                self.__current_state = None
                event.accept()
                return

    def changeConnectionEvent(self, event: QtCore.QEvent) -> None:
        state = cast(ChangeConnection, self.__current_state)

        if event.type() == QtCore.QEvent.MouseButtonPress:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                state.orig_connection = self.__scene.highlightedConnection()
                state.click_pos = self.mapToScene(mevent.pos())
                event.accept()
                return

        if event.type() in (QtCore.QEvent.MouseMove, ViewChange):
            if event.type() == QtCore.QEvent.MouseMove:
                mpos = cast(QtGui.QMouseEvent, event).pos()
            else:
                mpos = self.__mouse_pos

            if state.connection is None:
                delta = mpos - self.mapFromScene(state.click_pos)
                if delta.x() > 10:
                    # disconnect source
                    state.connection = DraggedConnection(
                        state.orig_connection.dest_port().handleScenePos(), True)
                    self.__scene.addItem(state.connection)
                    state.src_port = state.orig_connection.dest_port()
                    state.dest_port = None
                    state.orig_connection.setVisible(False)
                    self.__startConnectionDrag(state.src_port)
                    self.__scene.disableHighlights()

                elif delta.x() < -10:
                    # disconnect dest
                    state.connection = DraggedConnection(
                        state.orig_connection.src_port().handleScenePos(), False)
                    self.__scene.addItem(state.connection)
                    state.src_port = state.orig_connection.src_port()
                    state.dest_port = None
                    state.orig_connection.setVisible(False)
                    self.__startConnectionDrag(state.src_port)
                    self.__scene.disableHighlights()

            if state.connection is not None:
                dest_port = None  # type: base_node.Port
                min_dist = None  # type: float
                for item in self.__scene.items(self.senseRect(self.mapToScene(mpos), 32)):
                    if not isinstance(item, base_node.Port):
                        continue
                    if not state.src_port.canConnectTo(item):
                        continue

                    deltaF = item.scenePos() - self.mapToScene(mpos)
                    dist = QtCore.QPointF.dotProduct(deltaF, deltaF)
                    if min_dist is None or dist < min_dist:
                        dest_port = item
                        min_dist = dist

                self.__scene.setHighlightedPort(dest_port)

                state.connection.setSrcPos(state.src_port.handleScenePos())
                if dest_port is not None:
                    state.dest_port = dest_port
                    state.connection.setDestPos(dest_port.scenePos())
                else:
                    state.dest_port = None
                    state.connection.setDestPos(self.mapToScene(mpos))

            event.accept()
            return

        if event.type() == QtCore.QEvent.MouseButtonRelease:
            mevent = cast(QtGui.QMouseEvent, event)

            if mevent.button() == Qt.LeftButton:
                if state.dest_port is None:
                    # drop connection
                    with self.project.apply_mutations(
                            'Disconnect nodes %s and %s' % (
                                state.orig_connection.connection().source_node.name,
                                state.orig_connection.connection().dest_node.name)):
                        self.project.remove_node_connection(state.orig_connection.connection())

                elif (state.dest_port is state.orig_connection.dest_port()
                      or state.dest_port is state.orig_connection.src_port()):
                    # unchanged
                    state.orig_connection.setVisible(True)

                elif state.dest_port is not None:
                    # change
                    # TODO: this should be a sequence [delete, create]
                    with self.project.apply_mutations(
                            'Disconnect nodes %s and %s' % (
                                state.orig_connection.connection().source_node.name,
                                state.orig_connection.connection().dest_node.name)):
                        self.project.remove_node_connection(state.orig_connection.connection())

                    self.__scene.connectPorts(state.src_port, state.dest_port)

                if state.connection is not None:
                    self.__scene.removeItem(state.connection)

                self.__current_state = None
                self.__endConnectionDrag()
                event.accept()
                return

            if mevent.button() == Qt.RightButton:
                # abort drag
                state.orig_connection.setVisible(True)
                if state.connection is not None:
                    self.__scene.removeItem(state.connection)
                self.__current_state = None
                self.__endConnectionDrag()
                event.accept()
                return
