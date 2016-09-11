#!/usr/bin/python3

import functools
import logging
import math

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa import node_db
from . import ui_base
from . import dock_widget
from . import mute_button

logger = logging.getLogger(__name__)


class Port(QtWidgets.QGraphicsRectItem):
    def __init__(
            self, parent, node_id, port_desc):
        super().__init__(parent)
        self.node_id = node_id
        self.port_desc = port_desc

        self.setAcceptHoverEvents(True)

        self.setRect(0, 0, 45, 15)
        self.setBrush(Qt.white)

        if self.port_desc.direction == node_db.PortDirection.Input:
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

        if self.port_desc.port_type == node_db.PortType.Audio:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('A')
        elif self.port_desc.port_type == node_db.PortType.Control:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('C')
        elif self.port_desc.port_type == node_db.PortType.Events:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('E')
        else:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('?')
        sym.setPos(sym_pos)

    def getInfoText(self):
        return {
            (node_db.PortType.Audio, node_db.PortDirection.Input): "Audio Input port",
            (node_db.PortType.Audio, node_db.PortDirection.Output): "Audio Output port",
            (node_db.PortType.Control, node_db.PortDirection.Input): "Control Input port",
            (node_db.PortType.Control, node_db.PortDirection.Output): "Control Output port",
            (node_db.PortType.Events, node_db.PortDirection.Input): "Event Input port",
            (node_db.PortType.Events, node_db.PortDirection.Output): "Event Output port",
        }[(self.port_desc.port_type, self.port_desc.direction)]

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setBrush(QtGui.QColor(200, 200, 255))
        else:
            self.setBrush(Qt.white)

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        self.setHighlighted(True)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        self.setHighlighted(False)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.scene().view.startConnectionDrag(self)
            evt.accept()
            return

        return super().mousePressEvent(evt)


class QCloseIconItem(QtWidgets.QGraphicsObject):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.setAcceptHoverEvents(True)
        self.setOpacity(0.2)

        self._size = QtCore.QSizeF(16, 16)
        self._icon = QtGui.QIcon.fromTheme('edit-delete')

    def getInfoText(self):
        return "Remove this node."

    def boundingRect(self):
        return QtCore.QRectF(QtCore.QPointF(0, 0), self._size)

    def paint(self, painter, option, widget=None):
        self._icon.paint(painter, 0, 0, 16, 16)

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        self.setOpacity(1.0)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        self.setOpacity(0.4)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.clicked.emit()
            evt.accept()


class NodePropertyDock(ui_base.ProjectMixin, dock_widget.DockWidget):
    def __init__(self, node_item, **kwargs):
        super().__init__(
            identifier='node_properties:%s' % node_item.node.id,
            title="Node \"%s\" Properties" % node_item.node.name,
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            initial_floating=True,
            **kwargs)

        self._node_item = node_item

        layout = QtWidgets.QFormLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.setVerticalSpacing(1)

        self._name = QtWidgets.QLineEdit(self)
        self._name.setText(node_item.node.name)
        self._name.editingFinished.connect(self.onNameChanged)
        layout.addRow("Name", self._name)

        for port in self._node_item.node_description.ports:
            if not (port.direction == node_db.PortDirection.Output
                and port.port_type == node_db.PortType.Audio):
                continue

            port_property_values = dict(
                (p.name, p.value)
                for p in self._node_item.node.port_property_values
                if p.port_name == port.name)

            muted_widget = mute_button.MuteButton(self)
            muted_widget.setChecked(
                port_property_values.get('muted', False))
            volume_widget = QtWidgets.QDoubleSpinBox(
                self,
                suffix='%',
                minimum=0.0, maximum=1000.0, decimals=1,
                singleStep=5, accelerated=True)
            volume_widget.setEnabled(
                not port_property_values.get('muted', False))
            volume_widget.setValue(
                port_property_values.get('volume', 100.0))

            muted_widget.toggled.connect(functools.partial(
                self.onPortMutedChanged, port, volume_widget))
            volume_widget.valueChanged.connect(functools.partial(
                self.onPortVolumeChanged, port))

            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setSpacing(0)
            row_layout.addWidget(muted_widget)
            row_layout.addWidget(volume_widget, 1)
            layout.addRow(
                "Volume (port <i>%s</i>)" % port.name, row_layout)

            # TODO: port can be bypassable without dry/wet
            if port.drywet_port is not None:
                bypass_widget = QtWidgets.QToolButton(
                    self, checkable=True, autoRaise=True)
                bypass_widget.setText('B')
                bypass_widget.setChecked(
                    port_property_values.get('bypass', False))
                drywet_widget = QtWidgets.QSlider(
                    self,
                    minimum=-100, maximum=100,
                    orientation=Qt.Horizontal, tickInterval=20,
                    tickPosition=QtWidgets.QSlider.TicksBothSides)
                drywet_widget.setEnabled(
                    not port_property_values.get('bypass', False))
                drywet_widget.setValue(
                    int(port_property_values.get('drywet', 0.0)))

                bypass_widget.toggled.connect(functools.partial(
                    self.onPortBypassChanged, port, drywet_widget))
                drywet_widget.valueChanged.connect(functools.partial(
                    self.onPortDrywetChanged, port))

                row_layout = QtWidgets.QHBoxLayout()
                row_layout.setSpacing(0)
                row_layout.addWidget(bypass_widget)
                row_layout.addWidget(drywet_widget, 1)
                layout.addRow(
                    "Dry/wet (port <i>%s</i>)" % port.name, row_layout)

        parameter_values = dict(
            (p.name, p.value)
            for p in self._node_item.node.parameter_values)

        for parameter in self._node_item.node_description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                widget = QtWidgets.QLineEdit(self)
                widget.setText(str(parameter_values.get(
                    parameter.name, parameter.default)))
                widget.setValidator(QtGui.QDoubleValidator())
                widget.editingFinished.connect(functools.partial(
                    self.onFloatParameterChanged, widget, parameter))
                layout.addRow(parameter.display_name, widget)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(layout)
        self.setWidget(main_area)

    def onNameChanged(self):
        pass

    def onFloatParameterChanged(self, widget, parameter):
        value, ok = widget.locale().toDouble(widget.text())
        if ok:
            self.send_command_async(
                self._node_item.node.id, 'SetPipelineGraphNodeParameter',
                parameter_name=parameter.name,
                float_value=value)

    def onPortMutedChanged(self, port, volume_widget, value):
        volume_widget.setEnabled(not value)
        self.send_command_async(
            self._node_item.node.id, 'SetPipelineGraphPortParameter',
            port_name=port.name,
            muted=value)

    def onPortVolumeChanged(self, port, value):
        self.send_command_async(
            self._node_item.node.id, 'SetPipelineGraphPortParameter',
            port_name=port.name,
            volume=value)

    def onPortBypassChanged(self, port, volume_widget, value):
        volume_widget.setEnabled(not value)
        self.send_command_async(
            self._node_item.node.id, 'SetPipelineGraphPortParameter',
            port_name=port.name,
            bypass=value)

    def onPortDrywetChanged(self, port, value):
        self.send_command_async(
            self._node_item.node.id, 'SetPipelineGraphPortParameter',
            port_name=port.name,
            drywet=float(value))


class NodeItemImpl(QtWidgets.QGraphicsRectItem):
    def __init__(self, node, view, **kwargs):
        super().__init__(**kwargs)
        self._node = node
        self._view = view

        self._properties_dock = None

        self._listeners = []

        self._moving = False
        self._move_handle_pos = None
        self._moved = False

        self.setAcceptHoverEvents(True)

        self.setRect(0, 0, 100, 60)
        if False:  #self.desc.is_system:
            self.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 255)))
        else:
            self.setBrush(Qt.white)

        self.ports = {}
        self.connections = set()

        label = QtWidgets.QGraphicsSimpleTextItem(self)
        label.setPos(2, 2)
        label.setText(self._node.name)

        self._remove_icon = None

        if self._node.removable:
            self._remove_icon = QCloseIconItem(self)
            self._remove_icon.setPos(100 - 18, 2)
            self._remove_icon.setVisible(False)
            self._remove_icon.clicked.connect(self.onRemove)

        in_y = 25
        out_y = 25
        for port_desc in self._node.description.ports:
            if port_desc.direction == node_db.PortDirection.Input:
                x = -5
                y = in_y
                in_y += 20

            elif port_desc.direction == node_db.PortDirection.Output:
                x = 105-45
                y = out_y
                out_y += 20

            port = Port(
                self, self._node.id, port_desc)
            port.setPos(x, y)
            self.ports[port_desc.name] = port

        self.setPos(self._node.graph_pos.x, self._node.graph_pos.y)
        self._graph_pos_listener = self._node.listeners.add(
            'graph_pos', self.onGraphPosChanged)

    @property
    def node(self):
        return self._node

    @property
    def node_description(self):
        return self._node.description

    def getInfoText(self):
        info_lines = []

        parameter_values = dict(
            (p.name, p.value) for p in self._node.parameter_values)

        for parameter in self._node.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                value = parameter_values.get(
                    parameter.name, parameter.default)
                info_lines.append("%s: %s" % (
                    parameter.display_name, value))

        return '\n'.join(info_lines)

    def cleanup(self):
        if self._graph_pos_listener is not None:
            self._graph_pos_listener.remove()
            self._graph_pos_listener = None

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setBrush(QtGui.QColor(240, 240, 255))
        else:
            self.setBrush(Qt.white)

    def onGraphPosChanged(self, *args):
        self.setPos(self._node.graph_pos.x, self._node.graph_pos.y)
        for connection in self.connections:
            connection.update()

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        if self._remove_icon is not None:
            self._remove_icon.setVisible(True)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        if self._remove_icon is not None:
            self._remove_icon.setVisible(False)

    def mouseDoubleClickEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.onEdit(evt.screenPos())
            evt.accept()
        super().mouseDoubleClickEvent(evt)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self._view.nodeSelected.emit(self)

            self.grabMouse()
            self._moving = True
            self._move_handle_pos = evt.scenePos() - self.pos()
            self._moved = False
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        if self._moving:
            self.setPos(evt.scenePos() - self._move_handle_pos)
            for connection in self.connections:
                connection.update()
            self._moved = True
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if evt.button() == Qt.LeftButton and self._moving:
            if self._moved:
                self.send_command_async(
                    self._node.id, 'SetPipelineGraphNodePos',
                    graph_pos=music.Pos2F(self.pos().x(), self.pos().y()))

            self.ungrabMouse()
            self._moving = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()

        edit = menu.addAction("Edit properties...")
        edit.triggered.connect(lambda: self.onEdit(evt.screenPos()))

        if self._node.removable:
            remove = menu.addAction("Remove")
            remove.triggered.connect(self.onRemove)

        menu.exec_(evt.screenPos())
        evt.accept()

    def onRemove(self):
        self._view.send_command_async(
            self._node.parent.id, 'RemovePipelineGraphNode',
            node_id=self._node.id)

    def onEdit(self, pos=None):
        if self._properties_dock is None:
            self._properties_dock = NodePropertyDock(
                node_item=self,
                parent=self.window,
                initial_pos=pos,
                **self.context)
        self._properties_dock.show()

class NodeItem(ui_base.ProjectMixin, NodeItemImpl):
    pass


class ConnectionItemImpl(QtWidgets.QGraphicsPathItem):
    def __init__(self, connection=None, view=None, **kwargs):
        super().__init__(**kwargs)

        self._view = view
        self.connection = connection

        self.update()

    def update(self):
        node1_item = self._view.getNodeItem(
            self.connection.source_node.id)
        port1_item = node1_item.ports[self.connection.source_port]

        node2_item = self._view.getNodeItem(
            self.connection.dest_node.id)
        port2_item = node2_item.ports[self.connection.dest_port]

        pos1 = port1_item.mapToScene(port1_item.dot_pos)
        pos2 = port2_item.mapToScene(port2_item.dot_pos)
        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        self.setPath(path)

    def setHighlighted(self, highlighted):
        if highlighted:
            effect = QtWidgets.QGraphicsDropShadowEffect()
            effect.setBlurRadius(10)
            effect.setOffset(0, 0)
            effect.setColor(Qt.blue)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)

class ConnectionItem(ui_base.ProjectMixin, ConnectionItemImpl):
    pass


class DragConnection(QtWidgets.QGraphicsPathItem):
    def __init__(self, port):
        super().__init__()
        self.port = port

        self.end_pos = self.port.mapToScene(self.port.dot_pos)
        self.update()

    def setEndPos(self, pos):
        self.end_pos = pos
        self.update()

    def update(self):
        pos1 = self.port.mapToScene(self.port.dot_pos)
        pos2 = self.end_pos

        if self.port.port_desc.direction == node_db.PortDirection.Input:
            pos1, pos2 = pos2, pos1

        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        self.setPath(path)


class PipelineGraphSceneImpl(QtWidgets.QGraphicsScene):
    def __init__(self, view=None, **kwargs):
        super().__init__(**kwargs)
        self.view = view

    def helpEvent(self, evt):
        item = self.itemAt(evt.scenePos(), QtGui.QTransform())
        if (item is not None
            and isinstance(item, (NodeItem, Port, QCloseIconItem))):
            info_text = item.getInfoText()
            if info_text:
                QtWidgets.QToolTip.showText(
                    evt.screenPos(), info_text, self.view)
                evt.accept()
                return
        super().helpEvent(evt)

class PipelineGraphScene(ui_base.ProjectMixin, PipelineGraphSceneImpl):
    pass


class PipelineGraphGraphicsViewImpl(QtWidgets.QGraphicsView):
    nodeSelected = QtCore.pyqtSignal(object)

    def __init__(self, sheet, **kwargs):
        super().__init__(**kwargs)

        self._scene = PipelineGraphScene(view=self, **self.context)
        self.setScene(self._scene)

        self._sheet = sheet

        self._drag_connection = None
        self._drag_src_port = None
        self._drag_dest_port = None

        self._highlight_item = None

        self._nodes = []
        self._node_map = {}
        for node in self._sheet.pipeline_graph_nodes:
            item = NodeItem(node=node, view=self, **self.context)
            self._scene.addItem(item)
            self._nodes.append(item)
            self._node_map[node.id] = item

        self._pipeline_graph_nodes_listener = self._sheet.listeners.add(
            'pipeline_graph_nodes', self.onPipelineGraphNodesChange)

        self._connections = []
        for connection in self._sheet.pipeline_graph_connections:
            item = ConnectionItem(
                connection=connection, view=self, **self.context)
            self._scene.addItem(item)
            self._connections.append(item)
            self._node_map[connection.source_node.id].connections.add(item)
            self._node_map[connection.dest_node.id].connections.add(item)

        self._pipeline_graph_connections_listener = self._sheet.listeners.add(
            'pipeline_graph_connections',
            self.onPipelineGraphConnectionsChange)

        self.setAcceptDrops(True)

    def getNodeItem(self, node_id):
        return self._node_map[node_id]

    def onPipelineGraphNodesChange(self, action, *args):
        if action == 'insert':
            idx, node = args
            item = NodeItem(node=node, view=self, **self.context)
            self._scene.addItem(item)
            self._nodes.insert(idx, item)
            self._node_map[node.id] = item

        elif action == 'delete':
            idx, node = args
            item = self._nodes[idx]
            assert not item.connections, item.connections
            item.cleanup()
            self._scene.removeItem(item)
            del self._nodes[idx]
            del self._node_map[node.id]
            if self._highlight_item is item:
                self._highlight_item = None

        else:  # pragma: no cover
            raise AssertionError("Unknown action %r" % action)

    def onPipelineGraphConnectionsChange(self, action, *args):
        if action == 'insert':
            idx, connection = args
            item = ConnectionItem(
                connection=connection, view=self, **self.context)
            self._scene.addItem(item)
            self._connections.insert(idx, item)
            self._node_map[connection.source_node.id].connections.add(item)
            self._node_map[connection.dest_node.id].connections.add(item)

        elif action == 'delete':
            idx, connection = args
            item = self._connections[idx]
            self._scene.removeItem(item)
            del self._connections[idx]
            self._node_map[connection.source_node.id].connections.remove(item)
            self._node_map[connection.dest_node.id].connections.remove(item)
            if self._highlight_item is item:
                self._highlight_item = None

        else:  # pragma: no cover
            raise AssertionError("Unknown action %r" % action)

    def startConnectionDrag(self, port):
        assert self._drag_connection is None
        self._drag_connection = DragConnection(port)
        self._drag_src_port = port
        self._drag_dest_port = None
        self._scene.addItem(self._drag_connection)

    def mousePressEvent(self, evt):
        if (self._highlight_item is not None
            and isinstance(self._highlight_item, ConnectionItem)
            and evt.button() == Qt.LeftButton
            and evt.modifiers() == Qt.ShiftModifier):
            self.send_command_async(
                self._sheet.id, 'RemovePipelineGraphConnection',
                connection_id=self._highlight_item.connection.id)
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        scene_pos = self.mapToScene(evt.pos())

        if self._drag_connection is not None:
            snap_pos = scene_pos

            src_port = self._drag_src_port
            closest_port = None
            closest_dist = None
            for node_item in self._nodes:
                for port_name, port_item in sorted(node_item.ports.items()):
                    src_desc = src_port.port_desc
                    dest_desc = port_item.port_desc

                    if dest_desc.port_type != src_desc.port_type:
                        continue
                    if dest_desc.direction == src_desc.direction:
                        continue

                    port_pos = port_item.mapToScene(port_item.dot_pos)
                    dx = port_pos.x() - scene_pos.x()
                    dy = port_pos.y() - scene_pos.y()
                    dist = math.sqrt(dx*dx + dy*dy)
                    if dist > 30:
                        continue

                    if closest_port is None or dist < closest_dist:
                        closest_dist = dist
                        closest_port = port_item

            if closest_port is not None:
                snap_pos = closest_port.mapToScene(closest_port.dot_pos)

            self._drag_connection.setEndPos(snap_pos)

            if closest_port is not self._drag_dest_port:
                if self._drag_dest_port is not None:
                    self._drag_dest_port.setHighlighted(False)
                    self._drag_dest_port = None

                if closest_port is not None:
                    closest_port.setHighlighted(True)
                    self._drag_dest_port = closest_port

            evt.accept()
            return

        highlight_item = None
        cursor_rect = QtCore.QRectF(
            scene_pos - QtCore.QPointF(5, 5),
            scene_pos + QtCore.QPointF(5, 5))
        for item in self._scene.items(cursor_rect):
            if isinstance(item, (NodeItem, ConnectionItem)):
                highlight_item = item
                break

        if highlight_item is not self._highlight_item:
            if self._highlight_item is not None:
                self._highlight_item.setHighlighted(False)
                self._highlight_item = None

            if highlight_item is not None:
                highlight_item.setHighlighted(True)
                self._highlight_item = highlight_item

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if (evt.button() == Qt.LeftButton
            and self._drag_connection is not None):
            self._scene.removeItem(self._drag_connection)
            self._drag_connection = None

            if self._drag_dest_port is not None:
                self._drag_src_port.setHighlighted(False)
                self._drag_dest_port.setHighlighted(False)

                if self._drag_src_port.port_desc.direction != node_db.PortDirection.Output:
                    self._drag_src_port, self._drag_dest_port = self._drag_dest_port, self._drag_src_port

                assert self._drag_src_port.port_desc.direction == node_db.PortDirection.Output
                assert self._drag_dest_port.port_desc.direction == node_db.PortDirection.Input

                self.send_command_async(
                    self._sheet.id, 'AddPipelineGraphConnection',
                    source_node_id=self._drag_src_port.node_id,
                    source_port_name=self._drag_src_port.port_desc.name,
                    dest_node_id=self._drag_dest_port.node_id,
                    dest_port_name=self._drag_dest_port.port_desc.name)

            self._drag_src_port = None
            self._drag_dest_port = None

            evt.accept()
            return

        super().mouseReleaseEvent(evt)

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
            node_uri = bytes(data).decode('utf-8')

            drop_pos = self.mapToScene(evt.pos())
            self.send_command_async(
                self._sheet.id, 'AddPipelineGraphNode',
                uri=node_uri,
                graph_pos=music.Pos2F(drop_pos.x(), drop_pos.y()))

            evt.acceptProposedAction()

class PipelineGraphGraphicsView(
        ui_base.ProjectMixin, PipelineGraphGraphicsViewImpl):
    pass


class NodesList(ui_base.CommonMixin, QtWidgets.QListWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setDragDropMode(
            QtWidgets.QAbstractItemView.DragOnly)

        for uri, node_desc in self.app.node_db.nodes:
            list_item = QtWidgets.QListWidgetItem()
            list_item.setText(node_desc.display_name)
            list_item.setData(Qt.UserRole, uri)
            self.addItem(list_item)

    def mimeData(self, items):
        assert len(items) == 1
        item = items[0]
        data = item.data(Qt.UserRole).encode('utf-8')
        mime_data = QtCore.QMimeData()
        mime_data.setData(
            'application/x-noisicaa-pipeline-graph-node', data)
        return mime_data


class NodeListDock(dock_widget.DockWidget):
    def __init__(self, **kwargs):
        super().__init__(
            identifier='node_list',
            title="Available Nodes",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._node_list = NodesList(parent=self, **self.context)

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

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.setSpacing(0)
        layout.addWidget(self._node_filter)
        layout.addWidget(self._node_list, 1)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(layout)
        self.setWidget(main_area)

    def onNodeFilterChanged(self, text):
        for idx in range(self._node_list.count()):
            item = self._node_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)


class PipelineGraphViewImpl(QtWidgets.QWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._graph_view = PipelineGraphGraphicsView(
            sheet=self.sheet, **self.context)

        self._node_list_dock = NodeListDock(
            parent=self.window, **self.common_context)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.addWidget(self._graph_view)
        self.setLayout(layout)

    @property
    def sheet(self):
        return self.project.sheets[0]

    def showEvent(self, evt):
        self._node_list_dock.show()

    def hideEvent(self, evt):
        self._node_list_dock.hide()

class PipelineGraphView(ui_base.ProjectMixin, PipelineGraphViewImpl):
    pass
