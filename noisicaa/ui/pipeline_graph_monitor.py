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

import logging
import random

import toposort

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import node_db
from noisicaa.core import ipc
from . import ui_base

logger = logging.getLogger(__name__)


class AudioProcClient(audioproc.AudioProcClientMixin):
    def __init__(self, monitor):
        super().__init__()
        self.event_loop = monitor.event_loop
        self.monitor = monitor
        self.server = ipc.Server(
            self.event_loop, 'audioproc_monitor', socket_dir=self.monitor.app.process.tmp_dir)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()

    def handle_pipeline_mutation(self, mutation):
        self.monitor.onPipelineMutation(mutation)

    def handle_pipeline_status(self, status):
        self.monitor.onPipelineStatus(status)


class Port(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent, node_id, description):
        super().__init__(parent)
        self.node_id = node_id
        self.description = description

        self.setRect(0, 0, 45, 15)
        self.setBrush(Qt.white)

        if self.port_direction == node_db.PortDirection.Input:
            self.dot_pos = QtCore.QPoint(7, 7)
        else:
            self.dot_pos = QtCore.QPoint(45-7, 7)

        dot = QtWidgets.QGraphicsRectItem(self)
        dot.setRect(-1, -1, 3, 3)
        dot.setPos(self.dot_pos)
        dot.setBrush(Qt.black)

    @property
    def port_name(self):
        return self.description.name

    @property
    def port_direction(self):
        return self.description.direction


class Node(QtWidgets.QGraphicsRectItem):
    def __init__(self, node_id, description):
        super().__init__()
        self.node_id = node_id
        self.description = description

        self.setFlag(self.ItemSendsGeometryChanges, True)

        self.setRect(0, 0, 100, 60)
        if isinstance(self.description, node_db.SystemNodeDescription):
            self.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 255)))
        else:
            self.setBrush(Qt.white)

        self.ports = {}
        self.connections = set()

        label = QtWidgets.QGraphicsTextItem(self)
        label.setPos(2, 2)
        label.setPlainText(node_id)

        in_y = 25
        out_y = 25
        for port_desc in self.description.ports:
            if port_desc.direction == node_db.PortDirection.Input:
                x = -5
                y = in_y
                in_y += 20

            elif port_desc.direction == node_db.PortDirection.Output:
                x = 105-45
                y = out_y
                out_y += 20

            port = Port(self, self.node_id, port_desc)
            port.setPos(x, y)
            self.ports[port_desc.name] = port

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            for connection in self.connections:
                connection.update()

        return super().itemChange(change, value)


class Connection(QtWidgets.QGraphicsLineItem):
    def __init__(self, node1, port1, node2, port2):
        super().__init__()
        self.node1 = node1
        self.port1 = port1
        self.node2 = node2
        self.port2 = port2

        self.update()

    def update(self):
        pos1 = self.port1.mapToScene(self.port1.dot_pos)
        pos2 = self.port2.mapToScene(self.port2.dot_pos)
        self.setLine(QtCore.QLineF(pos1, pos2))


class PipelineGraphMonitor(ui_base.CommonMixin, QtWidgets.QMainWindow):
    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(self, app):
        super().__init__(app=app)

        self.setWindowTitle("noisicaä - Pipeline Graph Monitor")
        self.resize(600, 300)

        self.__windows = []
        self.__current_project_view = None
        self.__audioproc_client = None

        self.project_selector = QtWidgets.QComboBox()
        self.project_selector.currentIndexChanged.connect(self.onProjectChanged)

        self.zoomInAction = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('zoom-in'),
            "Zoom In",
            self, triggered=self.onZoomIn)
        self.zoomOutAction = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('zoom-out'),
            "Zoom Out",
            self, triggered=self.onZoomOut)

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.addWidget(self.project_selector)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoomInAction)
        self.toolbar.addAction(self.zoomOutAction)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.nodes = {}
        self.connections = {}

        self.scene = QtWidgets.QGraphicsScene()
        self.graph_view = QtWidgets.QGraphicsView(self.scene, self)
        self.graph_view.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.graph_view.setDragMode(
            QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setCentralWidget(self.graph_view)

        self.setVisible(
            int(self.app.settings.value(
                'dialog/pipeline_graph_monitor/visible', False)))
        self.restoreGeometry(
            self.app.settings.value(
                'dialog/pipeline_graph_monitor/geometry', b''))

    def storeState(self):
        s = self.app.settings
        s.beginGroup('dialog/pipeline_graph_monitor')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.endGroup()

    def showEvent(self, event):
        self.visibilityChanged.emit(True)
        super().showEvent(event)

    def hideEvent(self, event):
        self.visibilityChanged.emit(False)
        super().hideEvent(event)

    def onZoomIn(self):
        pass

    def onZoomOut(self):
        pass

    def onProjectListChanged(self):
        self.project_selector.clear()

        for win in self.__windows:
            for project_view in win.listProjectViews():
                self.project_selector.addItem(
                    project_view.project_connection.name,
                    project_view)
                if project_view is self.__current_project_view:
                    self.project_selector.setCurrentIndex(self.project_selector.count())

    def onProjectChanged(self, index):
        project_view = self.project_selector.itemData(index)
        if project_view is self.__current_project_view:
            return

        self.call_async(self.changeProject(project_view))

    async def changeProject(self, project_view):
        if self.__current_project_view is not None:
            self.scene.clear()
            self.__current_project_view = None

        if self.__audioproc_client is not None:
            await self.__audioproc_client.disconnect(shutdown=False)
            await self.__audioproc_client.cleanup()
            self.__audioproc_client = None

        if project_view is not None:
            self.__audioproc_client = AudioProcClient(self)
            await self.__audioproc_client.setup()
            await self.__audioproc_client.connect(project_view.player_audioproc_address)

            self.__current_project_view = project_view

    def addWindow(self, win):
        self.__windows.append(win)
        win.projectListChanged.connect(self.onProjectListChanged)
        self.onProjectListChanged()

    def onPipelineMutation(self, mutation):
        if isinstance(mutation, audioproc.AddNode):
            node = Node(mutation.id, mutation.node_description)
            node.setPos(random.randint(-200, 200), random.randint(-200, 200))
            self.scene.addItem(node)
            self.nodes[mutation.id] = node

        elif isinstance(mutation, audioproc.RemoveNode):
            node = self.nodes[mutation.id]
            self.scene.removeItem(node)
            del self.nodes[mutation.id]

        elif isinstance(mutation, audioproc.ConnectPorts):
            connection_id = '%s:%s-%s-%s' % (
                mutation.node1, mutation.port1,
                mutation.node2, mutation.port2)

            node1 = self.nodes[mutation.node1]
            node2 = self.nodes[mutation.node2]
            port1 = node1.ports[mutation.port1]
            port2 = node2.ports[mutation.port2]

            connection = Connection(node1, port1, node2, port2)
            self.scene.addItem(connection)
            self.connections[connection_id] = connection
            node1.connections.add(connection)
            node2.connections.add(connection)

        elif isinstance(mutation, audioproc.DisconnectPorts):
            connection_id = '%s:%s-%s-%s' % (
                mutation.node1, mutation.port1,
                mutation.node2, mutation.port2)

            connection = self.connections[connection_id]
            self.scene.removeItem(connection)
            del self.connections[connection_id]
            connection.node1.connections.remove(connection)
            connection.node2.connections.remove(connection)

        else:
            logger.warning("Unknown mutation received: %s", mutation)

        graph = {}
        for node in self.nodes.values():
            graph[node.node_id] = set()

        for connection in self.connections.values():
            graph[connection.node2.node_id].add(connection.node1.node_id)

        try:
            sorted_nodes = list(toposort.toposort(graph))
        except ValueError as exc:
            logger.error("Sorting audio proc graph failed: %s", exc)
        else:
            x = 0
            for layer in sorted_nodes:
                y = 0
                for node_id in sorted(layer):
                    node = self.nodes[node_id]
                    node.setPos(x, y)
                    y += 150
                x += 200

    def onPipelineStatus(self, status):
        logger.info("onPipelineStatus(%s)", status)
