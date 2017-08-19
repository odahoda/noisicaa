#!/usr/bin/python3

import asyncio
import sys
import argparse
import logging
import random
import functools

import quamash
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

from noisicaa.core import ipc
from noisicaa.audioproc import mutations
from noisicaa.audioproc import audioproc_client
from noisicaa.audioproc import audioproc_process
from noisicaa.ui import load_history

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

    def handle_pipeline_status(self, status):
        self.window.handle_pipeline_status(status)


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
                await client.set_backend('pyaudio')

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
                self.set_selected(True)
                self.scene().select_port(
                    self.node_id, self.port_name, self.port_direction)
            else:
                self.set_selected(False)
                self.scene().unselect_port(
                    self.node_id, self.port_name)

        return super().mousePressEvent(evt)


class Node(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent, node_id, desc):
        super().__init__(parent)
        self.node_id = node_id
        self.desc = desc

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

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            for connection in self.connections:
                connection.update()

        return super().itemChange(change, value)

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()
        if not self.desc.is_system:
            remove = menu.addAction("Remove")
            remove.triggered.connect(self.onRemove)
        menu.exec_(evt.screenPos())
        evt.accept()

    def onRemove(self):
        for connection in self.connections:
            task = self.scene().window.event_loop.create_task(
                self.scene().window.client.disconnect_ports(
                    connection.node1.node_id, connection.port1.port_name,
                    connection.node2.node_id, connection.port2.port_name))
            task.add_done_callback(
                functools.partial(
                    self.scene().window.command_done_callback,
                    command="Disconnect ports %s:%s-%s:%s" % (
                        connection.node1.desc.name,
                        connection.port1.port_name,
                        connection.node2.desc.name,
                        connection.port2.port_name)))

        task = self.scene().window.event_loop.create_task(
            self.scene().window.client.remove_node(self.node_id))
        task.add_done_callback(
            functools.partial(
                self.scene().window.command_done_callback,
                command="Remove node %s" % self.desc.name))


class Connection(QtWidgets.QGraphicsLineItem):
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
        self.setLine(QtCore.QLineF(pos1, pos2))


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
            node1 = self.window.nodes[self.selected_port1[0]]
            port1 = node1.ports[self.selected_port1[1]]
            node2 = self.window.nodes[self.selected_port2[0]]
            port2 = node2.ports[self.selected_port2[1]]
            connection_id = '%s:%s-%s-%s' % (
                *self.selected_port1, *self.selected_port2)
            if connection_id in self.window.connections:
                task = self.window.event_loop.create_task(
                    self.window.client.disconnect_ports(
                        *self.selected_port1, *self.selected_port2))
                task.add_done_callback(
                    functools.partial(
                        self.window.command_done_callback,
                        command="Disconnect ports %s:%s-%s:%s" % (
                            node1.desc.name, port1.port_name,
                            node2.desc.name, port2.port_name)))
            else:
                task = self.window.event_loop.create_task(
                    self.window.client.connect_ports(
                        *self.selected_port1, *self.selected_port2))
                task.add_done_callback(
                    functools.partial(
                        self.window.command_done_callback,
                        command="Connect ports %s:%s-%s:%s" % (
                            node1.desc.name, port1.port_name,
                            node2.desc.name, port2.port_name)))

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


class QPathLineEdit(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        action = self.addAction(
            QtGui.QIcon.fromTheme('document-open'),
            self.TrailingPosition)
        action.triggered.connect(self._selectFile)

    def _selectFile(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Select path...",
            directory=self.text())
        if not path:
            return
        self.setText(path)

class CreateNodeWindow(QtWidgets.QDialog):
    def __init__(self, window, node_type):
        super().__init__(window)

        self.window = window
        self.node_type = node_type

        self.setWindowTitle("Create {} node".format(self.node_type.name))
        self.setModal(True)

        playout = QtWidgets.QFormLayout()

        self.widgets = {}
        for pname, ptype in self.node_type.parameters:
            if ptype == 'float':
                widget = QtWidgets.QLineEdit(self)
                widget.setText('0.0')
                widget.setValidator(QtGui.QDoubleValidator())
                playout.addRow(pname, widget)

            elif ptype == 'int':
                widget = QtWidgets.QLineEdit(self)
                widget.setText('0')
                widget.setValidator(QtGui.QIntValidator())
                playout.addRow(pname, widget)

            elif ptype == 'path':
                widget = QPathLineEdit(self)
                playout.addRow(pname, widget)

            else:
                raise ValueError("Unsupported parameter type %r" % ptype)

            self.widgets[pname] = widget

        create_button = QtWidgets.QPushButton("Create")
        create_button.setDefault(True)
        create_button.clicked.connect(self.create_node)

        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(lambda: self.done(0))

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(playout, stretch=1)
        blayout = QtWidgets.QHBoxLayout()
        blayout.addStretch(1)
        blayout.addWidget(create_button)
        blayout.addWidget(cancel_button)
        layout.addLayout(blayout)
        self.setLayout(layout)

    def create_node(self):
        args = {}
        for pname, ptype in self.node_type.parameters:
            widget = self.widgets[pname]
            if ptype == 'float':
                value, _ = widget.locale().toDouble(widget.text())
            elif ptype == 'int':
                value, _ = widget.locale().toInt(widget.text())
            elif ptype == 'path':
                value = widget.text()
            else:
                raise ValueError("Unsupported parameter type %r" % ptype)

            args[pname] = value

        task = self.window.event_loop.create_task(
            self.window.client.add_node(self.node_type.name, **args))
        task.add_done_callback(
            functools.partial(
                self.window.command_done_callback,
                command="Create node %s" % self.node_type.name))
        self.done(0)


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

        statusbar = QtWidgets.QStatusBar()

        self.pipeline_status = load_history.LoadHistoryWidget(100, 30)
        self.pipeline_status.setToolTip("Load of the playback engine.")
        statusbar.addPermanentWidget(self.pipeline_status)

        self.setStatusBar(statusbar)

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

    def command_done_callback(self, task, command):
        exc = task.exception()
        if exc is not None:
            logger.error("Command %s failed: %s", command, exc)
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Command failed")
            msg.setText(command)
            msg.setInformativeText(str(exc))
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setModal(True)
            msg.show()

    def set_node_types(self, node_types):
        self.node_type_list.clear()
        for node_type in node_types:
            item = QtWidgets.QListWidgetItem()
            item.setText(node_type.name)
            item.setData(Qt.UserRole, node_type)
            self.node_type_list.addItem(item)

    def doubleClicked(self, item):
        node_type = item.data(Qt.UserRole)
        if len(node_type.parameters) > 0:
            win = CreateNodeWindow(self, node_type)
            win.show()

        else:
            task = self.event_loop.create_task(
                self.client.add_node(node_type.name))
            task.add_done_callback(
                functools.partial(
                    self.command_done_callback,
                    command="Create node %s" % node_type.name))

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

            connection = Connection(None, node1, port1, node2, port2)
            self.scene.addItem(connection)
            self.connections[connection_id] = connection
            node1.connections.add(connection)
            node2.connections.add(connection)

        elif isinstance(mutation, mutations.DisconnectPorts):
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

    def handle_pipeline_status(self, status):
        if 'utilization' in status:
            self.pipeline_status.addValue(status['utilization'])


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

    def app_complete_callback(task):
        exc = task.exception
        if exc is not None:
            logger.error("%s", exc)
            event_loop.stop()

    with event_loop:
        task = event_loop.create_task(app.main(event_loop))
        task.add_done_callback(app_complete_callback)
        event_loop.run_forever()

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
