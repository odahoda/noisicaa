#!/usr/bin/python3

import pyximport
pyximport.install()

import asyncio
import sys
import argparse
import logging
import random

from quamash import QEventLoop
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMainWindow,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QWidget,
)
from PyQt5.QtGui import (
    QKeySequence,
)

from noisicaa.core import ipc
from noisicaa.audioproc import mutations
from noisicaa.audioproc import audioproc_client
from noisicaa.audioproc import audioproc_process


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


class AudioPlaygroundApp(QApplication):
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


class Node(QGraphicsTextItem):
    def __init__(self):
        pass


class AudioPlaygroundWindow(QMainWindow):
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
        project_menu.addAction(QAction(
            "Quit", self,
            shortcut=QKeySequence.Quit, shortcutContext=Qt.ApplicationShortcut,
            statusTip="Quit the application",
            triggered=self.close_event.set))

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self)
        self.view.setScene(self.scene)

        self.node_type_list = QListWidget(self)
        self.node_type_list.itemDoubleClicked.connect(self.doubleClicked)

        layout = QHBoxLayout()
        layout.addWidget(self.view)
        layout.addWidget(self.node_type_list)

        central_widget = QWidget(self)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def closeEvent(self, evt):
        self.close_event.set()
        return super().closeEvent(evt)

    def set_node_types(self, node_types):
        self.node_type_list.clear()
        for node_type in node_types:
            item = QListWidgetItem()
            item.setText(node_type.name)
            item.setData(Qt.UserRole, node_type)
            self.node_type_list.addItem(item)

    def doubleClicked(self, item):
        node_type = item.data(Qt.UserRole)
        self.event_loop.create_task(self.client.add_node(node_type.name))

    def handle_pipeline_mutation(self, mutation):
        if isinstance(mutation, mutations.AddNode):
            node = QGraphicsRectItem()
            node.setPos(random.randint(-200, 200), random.randint(-200, 200))
            node.setRect(0, 0, 100, 60)

            label = QGraphicsTextItem(node)
            label.setPos(2, 2)
            label.setPlainText(mutation.name)

            self.scene.addItem(node)
            self.nodes[mutation.id] = node

        elif isinstance(mutation, mutations.RemoveNode):
            node = self.nodes[mutation.id]
            self.scene.removeItem(node)
            del self.nodes[mutation.id]

        elif isinstance(mutation, mutations.ConnectPorts):
            pass
        elif isinstance(mutation, mutations.DisconnectPorts):
            pass
        else:
            logging.warning("Unknown mutation received: %s", mutation)


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
    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    with event_loop:
        event_loop.create_task(app.main(event_loop))
        event_loop.run_forever()

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
