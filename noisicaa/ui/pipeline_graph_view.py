#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.audioproc import node_types
from . import ui_base

logger = logging.getLogger(__name__)


class Port(QtWidgets.QGraphicsRectItem):
    def __init__(
            self, parent, node_id, port_name, port_direction, port_type):
        super().__init__(parent)
        self.node_id = node_id
        self.port_name = port_name
        self.port_direction = port_direction
        self.port_type = port_type

        self.setRect(0, 0, 45, 15)
        self.setBrush(Qt.white)

        if self.port_direction == 'input':
            self.dot_pos = QtCore.QPoint(7, 7)
            sym_pos = QtCore.QPoint(45-11, -1)
        else:
            self.dot_pos = QtCore.QPoint(45-7, 7)
            sym_pos = QtCore.QPoint(3, -1)

        path = QtGui.QPainterPath()
        path.moveTo(-5, -5)
        path.lineTo(-5, 5)
        path.lineTo(5, 0)
        path.closeSubpath()
        dot = QtWidgets.QGraphicsPathItem(self)
        dot.setPath(path)
        dot.setPos(self.dot_pos)
        dot.setBrush(Qt.black)
        dot.pen().setStyle(Qt.NoPen)

        if self.port_type == 'audio':
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('A')
        elif self.port_type == 'events':
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('E')
        else:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('?')
        sym.setPos(sym_pos)

        self.selected = False

    def set_selected(self, selected):
        if selected:
            self.setBrush(Qt.red)
        else:
            self.setBrush(Qt.white)
        self.selected = selected

    def mousePressEvent(self, evt):
        if evt.buttons() & Qt.LeftButton:
            if not self.selected:
                self.set_selected(True)
                self.scene().select_port(
                    self.node_id, self.port_name, self.port_direction)
            else:
                self.set_selected(False)
                self.scene().unselect_port(
                    self.node_id, self.port_name)

        return super().mousePressEvent(evt)


class QCloseIconItem(QtWidgets.QGraphicsObject):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.setAcceptHoverEvents(True)
        self.setOpacity(0.2)

        self._size = QtCore.QSizeF(16, 16)
        self._icon = QtGui.QIcon.fromTheme('edit-delete')

    def boundingRect(self):
        return QtCore.QRectF(QtCore.QPointF(0, 0), self._size)

    def paint(self, painter, option, widget=None):
        self._icon.paint(painter, 0, 0, 16, 16)

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        self.setOpacity(1.0)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        self.setOpacity(0.2)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.clicked.emit()
            evt.accept()


class Node(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent, node_id, desc):
        super().__init__(parent)
        self.node_id = node_id
        self.desc = desc

        self.setAcceptHoverEvents(True)
        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemSendsGeometryChanges, True)
        self.setFlag(self.ItemIsSelectable, True)

        self.setRect(0, 0, 100, 60)
        if self.desc.is_system:
            self.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 255)))
        else:
            self.setBrush(Qt.white)

        self.ports = {}
        self.connections = set()

        label = QtWidgets.QGraphicsSimpleTextItem(self)
        label.setPos(2, 2)
        label.setText(self.desc.name)

        self._remove_icon = QCloseIconItem(self)
        self._remove_icon.setPos(100 - 18, 2)
        self._remove_icon.setVisible(False)
        self._remove_icon.clicked.connect(self.onRemove)

        in_y = 25
        out_y = 25
        for port_name, port_direction, port_type in self.desc.ports:
            if port_direction == 'input':
                x = -5
                y = in_y
                in_y += 20

            elif port_direction == 'output':
                x = 105-45
                y = out_y
                out_y += 20

            port = Port(
                self, self.node_id, port_name, port_direction, port_type)
            port.setPos(x, y)
            self.ports[port_name] = port

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            for connection in self.connections:
                connection.update()

        return super().itemChange(change, value)

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        self._remove_icon.setVisible(True)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        self._remove_icon.setVisible(False)

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()
        if not self.desc.is_system:
            remove = menu.addAction("Remove")
            remove.triggered.connect(self.onRemove)
        menu.exec_(evt.screenPos())
        evt.accept()

    def onRemove(self):
        for connection in self.connections:
            if connection.node1 is not self:
                connection.node1.connections.remove(connection)
            if connection.node2 is not self:
                connection.node2.connections.remove(connection)

            self.scene().removeItem(connection)

        self.scene().removeItem(self)


class Connection(QtWidgets.QGraphicsPathItem):
    def __init__(self, parent, node1, port1, node2, port2):
        super().__init__(parent)
        self.node1 = node1
        self.port1 = port1
        self.node2 = node2
        self.port2 = port2

        self.update()

    def update(self):
        pos1 = self.port1.mapToScene(self.port1.dot_pos)
        pos2 = self.port2.mapToScene(self.port2.dot_pos)
        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cx, pos2 - cx, pos2)
        self.setPath(path)


class PipelineGraphSceneImpl(QtWidgets.QGraphicsScene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        desc = node_types.NodeType()
        desc.name = "Node 1"
        desc.port('in', 'input', 'audio')
        desc.port('out', 'output', 'audio')
        node1 = Node(None, '1', desc)
        self.addItem(node1)

        desc = node_types.NodeType()
        desc.name = "Node 2"
        desc.port('in', 'input', 'audio')
        desc.port('out', 'output', 'audio')
        node2 = Node(None, '2', desc)
        self.addItem(node2)

        connection = Connection(
            None, node1, node1.ports['out'], node2, node2.ports['in'])
        self.addItem(connection)
        #self.connections[connection_id] = connection
        node1.connections.add(connection)
        node2.connections.add(connection)

class PipelineGraphScene(ui_base.ProjectMixin, PipelineGraphSceneImpl):
    pass


class PipelineGraphGraphicsViewImpl(QtWidgets.QGraphicsView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._scene = PipelineGraphScene(**self.context)
        self.setScene(self._scene)

        self.setAcceptDrops(True)

    def dragEnterEvent(self, evt):
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            evt.setDropAction(Qt.CopyAction)
            evt.accept()

    def dragMoveEvent(self, evt):
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            evt.acceptProposedAction()

    def dragLeaveEvent(self, evt):
        evt.accept()

    def dropEvent(self, evt):
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            data = evt.mimeData().data(
                'application/x-noisicaa-pipeline-graph-node')
            nodes = bytes(data).decode('utf-8').split('\n')

            for node_name in nodes:
                desc = node_types.NodeType()
                desc.name = node_name
                desc.port('in', 'input', 'audio')
                desc.port('out', 'output', 'audio')
                node = Node(None, '1', desc)
                node.setPos(self.mapToScene(evt.pos()))
                self._scene.addItem(node)

            evt.acceptProposedAction()

class PipelineGraphGraphicsView(
        ui_base.ProjectMixin, PipelineGraphGraphicsViewImpl):
    pass


class NodesList(QtWidgets.QListWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.setDragDropMode(
            QtWidgets.QAbstractItemView.DragOnly)
        self.addItem("Reverb")
        self.addItem("Compressor")
        self.addItem("Bitcrusher")

    def mimeData(self, items):
        data = '\n'.join(item.text() for item in items).encode('utf-8')
        mime_data = QtCore.QMimeData()
        mime_data.setData(
            'application/x-noisicaa-pipeline-graph-node', data)
        return mime_data


class PipelineGraphViewImpl(QtWidgets.QWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._graph_view = PipelineGraphGraphicsView(**self.context)

        self._node_list = NodesList()

        self._node_filter = QtWidgets.QLineEdit(self)
        self._node_filter.addAction(
            QtGui.QIcon.fromTheme('edit-find'),
            QtWidgets.QLineEdit.LeadingPosition)
        self._node_filter.addAction(
            QtWidgets.QAction(
                QtGui.QIcon.fromTheme('edit-clear'),
                "Clear search string", self._node_filter,
                triggered=self._node_filter.clear),
            QtWidgets.QLineEdit.TrailingPosition)
        self._node_filter.textChanged.connect(self.onNodeFilterChanged)

        side_layout = QtWidgets.QVBoxLayout()
        side_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        side_layout.addWidget(self._node_filter)
        side_layout.addWidget(self._node_list, 1)

        side_pane = QtWidgets.QWidget(self)
        side_pane.setLayout(side_layout)

        splitter = QtWidgets.QSplitter(self)
        splitter.addWidget(self._graph_view)
        splitter.addWidget(side_pane)
        splitter.setStretchFactor(0, 20)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.addWidget(splitter)
        self.setLayout(layout)

    def onNodeFilterChanged(self, text):
        for idx in range(self._node_list.count()):
            item = self._node_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

class PipelineGraphView(ui_base.ProjectMixin, PipelineGraphViewImpl):
    pass
