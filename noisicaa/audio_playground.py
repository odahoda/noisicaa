#!/usr/bin/python3

import pyximport
pyximport.install()

import asyncio
import sys
import argparse
import logging
import random

import quamash
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

from noisicaa.core import ipc
from noisicaa.audioproc import mutations
from noisicaa.audioproc import audioproc_client
from noisicaa.audioproc import audioproc_process


logger = logging.getLogger()


class AudioProcClientImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class AudioProcClient(
        audioproc_client.AudioProcClientMixin, AudioProcClientImpl):
    def __init__(self, event_loop, window):
        super().__init__(event_loop)
        self.window = window

    def handle_pipeline_mutation(self, mutation):
        self.window.handle_pipeline_mutation(mutation)


class AudioProcProcessImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'process')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class AudioProcProcess(
        audioproc_process.AudioProcProcessMixin, AudioProcProcessImpl):
    pass


class AudioPlaygroundApp(QtWidgets.QApplication):
    def __init__(self):
        super().__init__(['noisipg'])

    async def main(self, event_loop):
        audioproc = AudioProcProcess(event_loop)
        await audioproc.setup()
        try:
            window = AudioPlaygroundWindow(event_loop)
            client = AudioProcClient(event_loop, window)
            window.client = client
            await client.setup()
            try:
                await client.connect(audioproc.server.address)

                window.set_node_types(await client.list_node_types())

                window.show()
                await window.close_event.wait()
                self.quit()
            finally:
                await client.cleanup()
        finally:
            await audioproc.cleanup()


class Port(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent, node_id, port_name, port_direction):
        super().__init__(parent)
        self.node_id = node_id
        self.port_name = port_name
        self.port_direction = port_direction

        self.setRect(0, 0, 45, 15)
        self.setBrush(Qt.white)

        if self.port_direction == 'input':
            self.dot_pos = QtCore.QPoint(7, 7)
        else:
            self.dot_pos = QtCore.QPoint(45-7, 7)

        dot = QtWidgets.QGraphicsRectItem(self)
        dot.setRect(-1, -1, 3, 3)
        dot.setPos(self.dot_pos)
        dot.setBrush(Qt.black)

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
                self.scene().select_port(
                    self.node_id, self.port_name, self.port_direction)
                self.set_selected(True)
            else:
                self.scene().unselect_port(
                    self.node_id, self.port_name)
                self.set_selected(False)

        return super().mousePressEvent(evt)


class Node(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent, node_id, desc):
        super().__init__(parent)
        self.node_id = node_id
        self.desc = desc

        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemIsSelectable, True)

        self.setRect(0, 0, 100, 60)
        self.setBrush(Qt.white)

        self.ports = {}

        label = QtWidgets.QGraphicsTextItem(self)
        label.setPos(2, 2)
        label.setPlainText(self.desc.name)

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

            port = Port(self, self.node_id, port_name, port_direction)
            port.setPos(x, y)
            self.ports[port_name] = port

    #def mousePressEvent(self, evt):
    #    print(evt)
    #    return super().mousePressEvent(evt)


class Scene(QtWidgets.QGraphicsScene):
    def __init__(self, window):
        super().__init__()
        self.window = window

        self.selected_port1 = None
        self.selected_port2 = None

    def select_port(self, node_id, port_name, port_type):
        if port_type == 'output':
            if self.selected_port1 is not None:
                node = self.window.nodes[self.selected_port1[0]]
                port = node.ports[self.selected_port1[1]]
                port.set_selected(False)
            self.selected_port1 = (node_id, port_name)
        elif port_type == 'input':
            if self.selected_port2 is not None:
                node = self.window.nodes[self.selected_port2[0]]
                port = node.ports[self.selected_port2[1]]
                port.set_selected(False)
            self.selected_port2 = (node_id, port_name)

        if self.selected_port1 and self.selected_port2:
            self.window.event_loop.create_task(
                self.window.client.connect_ports(
                    *self.selected_port1, *self.selected_port2))
            node = self.window.nodes[self.selected_port1[0]]
            port = node.ports[self.selected_port1[1]]
            port.set_selected(False)
            self.selected_port1 = None
            node = self.window.nodes[self.selected_port2[0]]
            port = node.ports[self.selected_port2[1]]
            port.set_selected(False)
            self.selected_port2 = None

    def unselect_port(self, node_id, port_name):
        if (node_id, port_name) == self.selected_port1:
            self.selected_port1 = None
        if (node_id, port_name) == self.selected_port2:
            self.selected_port2 = None


class AudioPlaygroundWindow(QtWidgets.QMainWindow):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.client = None

        self.close_event = asyncio.Event()

        self.nodes = {}
        self.connections = {}

        self.setWindowTitle("noisicaä audio playground")
        self.resize(800, 600)

        menu_bar = self.menuBar()
        project_menu = menu_bar.addMenu("Project")
        project_menu.addAction(QtWidgets.QAction(
            "Quit", self,
            shortcut=QtGui.QKeySequence.Quit,
            shortcutContext=Qt.ApplicationShortcut,
            statusTip="Quit the application",
            triggered=self.close_event.set))

        self.scene = Scene(self)
        self.view = QtWidgets.QGraphicsView(self)
        self.view.setScene(self.scene)

        self.node_type_list = QtWidgets.QListWidget(self)
        self.node_type_list.itemDoubleClicked.connect(self.doubleClicked)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.view)
        layout.addWidget(self.node_type_list)

        central_widget = QtWidgets.QWidget(self)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def closeEvent(self, evt):
        self.close_event.set()
        return super().closeEvent(evt)

    def set_node_types(self, node_types):
        self.node_type_list.clear()
        for node_type in node_types:
            item = QtWidgets.QListWidgetItem()
            item.setText(node_type.name)
            item.setData(Qt.UserRole, node_type)
            self.node_type_list.addItem(item)

    def doubleClicked(self, item):
        node_type = item.data(Qt.UserRole)
        self.event_loop.create_task(self.client.add_node(node_type.name))

    def handle_pipeline_mutation(self, mutation):
        if isinstance(mutation, mutations.AddNode):
            node = Node(None, mutation.id, mutation.desc)
            node.setPos(random.randint(-200, 200), random.randint(-200, 200))
            self.scene.addItem(node)
            self.nodes[mutation.id] = node

        elif isinstance(mutation, mutations.RemoveNode):
            node = self.nodes[mutation.id]
            self.scene.removeItem(node)
            del self.nodes[mutation.id]

        elif isinstance(mutation, mutations.ConnectPorts):
            connection_id = '%s:%s-%s-%s' % (
                mutation.node1, mutation.port1,
                mutation.node2, mutation.port2)

            node1 = self.nodes[mutation.node1]
            node2 = self.nodes[mutation.node2]
            port1 = node1.ports[mutation.port1]
            port2 = node2.ports[mutation.port2]
            pos1 = port1.mapToScene(port1.dot_pos)
            pos2 = port2.mapToScene(port2.dot_pos)

            line = QtWidgets.QGraphicsLineItem()
            line.setLine(QtCore.QLineF(pos1, pos2))
            self.scene.addItem(line)
            self.connections[connection_id] = line

        elif isinstance(mutation, mutations.DisconnectPorts):
            connection_id = '%s:%s-%s-%s' % (
                mutation.node1, mutation.port1,
                mutation.node2, mutation.port2)

            connection = self.connections[connection_id]
            self.scene.removeItem(connection)
            del self.connections[connection_id]

        else:
            logger.warning("Unknown mutation received: %s", mutation)


def main(argv):
    parser = argparse.ArgumentParser(
        prog=argv[0])
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='error',
        help="Minimum level for log messages written to STDERR.")
    args = parser.parse_args(args=argv[1:])

    logging.basicConfig()
    logging.getLogger().setLevel({
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
        }[args.log_level])

    app = AudioPlaygroundApp()
    event_loop = quamash.QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    with event_loop:
        event_loop.create_task(app.main(event_loop))
        event_loop.run_forever()

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
