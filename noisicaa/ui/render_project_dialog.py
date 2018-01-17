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
import os.path
import threading

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

logger = logging.getLogger(__name__)


class RenderProjectDialog(QtWidgets.QDialog):
    def __init__(self, parent, app, project):
        super().__init__(parent)

        self._app = app
        self._project = project

        self._file_name_suffix = '.flac'

        self._renderer = None

        self.setWindowTitle("noisicaä - Render Project")

        self.top_area = QtWidgets.QWidget(self)

        self.select_output_directory = QtWidgets.QToolButton(
            self.top_area,
            icon=QtGui.QIcon.fromTheme('document-open'),
            autoRaise=True)
        self.select_output_directory.clicked.connect(self.onSelectOutputDirectory)

        self.output_directory = QtWidgets.QLineEdit(self.top_area, text="/tmp")

        self.file_name = QtWidgets.QLineEdit(self.top_area, text="test.flac")

        self.file_format = QtWidgets.QComboBox(self.top_area)
        self.file_format.addItem("FLAC", userData="flac")
        #self.file_format.addItem("OGG", userData="ogg")
        self.file_format.currentIndexChanged.connect(self.onFileFormatChanged)

        self.progress = QtWidgets.QProgressBar(
            self.top_area, minimum=0, maximum=100, visible=False)
        self.progress.setMinimumWidth(200)

        self.status = QtWidgets.QLabel(self, visible=False)
        font = QtGui.QFont(self.status.font())
        font.setWeight(QtGui.QFont.Bold)
        if font.pixelSize() != -1:
            font.setPixelSize(14 * font.pixelSize() // 10)
        else:
            font.setPointSizeF(1.4 * font.pointSizeF())
        self.status.setFont(font)

        self.abort_button = QtWidgets.QPushButton("Abort", visible=False)
        self.abort_button.clicked.connect(self.onAbort)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        self.render_button = QtWidgets.QPushButton("Render")
        self.render_button.clicked.connect(self.onRender)

        output_directory_layout = QtWidgets.QHBoxLayout(spacing=1)
        output_directory_layout.addWidget(self.output_directory, 1)
        output_directory_layout.addWidget(self.select_output_directory)

        top_layout = QtWidgets.QFormLayout()
        top_layout.addRow("Output Directory", output_directory_layout)
        top_layout.addRow("Filename", self.file_name)
        top_layout.addRow("Format", self.file_format)

        self.top_area.setLayout(top_layout)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.progress)
        buttons.addWidget(self.status)
        buttons.addWidget(self.abort_button)
        buttons.addStretch(1)
        buttons.addWidget(self.render_button)
        buttons.addWidget(self.close_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.top_area, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def onSelectOutputDirectory(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption="Select output directory...",
            directory=self.output_directory.text())
        if path is not None:
            self.output_directory.setText(path)

    def onFileFormatChanged(self, index):
        file_format = self.file_format.itemData(index)
        file_name_suffix = '.' + file_format
        if file_name_suffix != self._file_name_suffix:
            file_name = self.file_name.text()
            if file_name.lower().endswith(self._file_name_suffix):
                file_name = file_name[:-len(self._file_name_suffix)]
            self._file_name_suffix = file_name_suffix
            file_name += file_name_suffix
            self.file_name.setText(file_name)

    def onRender(self):
        assert self._renderer is None

        self.top_area.setEnabled(False)
        self.render_button.setEnabled(False)
        self.close_button.setEnabled(False)

        self.status.setVisible(False)
        self.progress.setVisible(True)
        self.abort_button.setVisible(True)

        self._renderer = Renderer(
            self._project,
            os.path.join(self.output_directory.text(), self.file_name.text()),
            self.file_format.currentData())
        self._renderer.progress.connect(self.progress.setValue)
        self._renderer.done.connect(self.onRendererDone)
        self._renderer.start()

    def onRendererDone(self):
        assert self._renderer is not None

        if self._renderer.status == Renderer.SUCCESS:
            self.status.setText("Done.")
            palette = QtGui.QPalette(self.status.palette())
            palette.setColor(
                QtGui.QPalette.WindowText, QtGui.QColor(60, 160, 60))
            self.status.setPalette(palette)
        elif self._renderer.status == Renderer.ABORTED:
            self.status.setText("Aborted")
            palette = QtGui.QPalette(self.status.palette())
            palette.setColor(
                QtGui.QPalette.WindowText, QtGui.QColor(255, 60, 60))
            self.status.setPalette(palette)
        elif self._renderer.status == Renderer.FAILED:
            self.status.setText("Failed!")
            palette = QtGui.QPalette(self.status.palette())
            palette.setColor(
                QtGui.QPalette.WindowText, QtGui.QColor(255, 60, 60))
            self.status.setPalette(palette)

            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Renderer failed")
            msg.setText("Rendering failed with an error:")
            msg.setInformativeText(self._renderer.reason)
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.addButton("Ok", QtWidgets.QMessageBox.AcceptRole)
            msg.exec_()

        self._renderer = None

        self.progress.setVisible(False)
        self.status.setVisible(True)
        self.abort_button.setVisible(False)
        self.top_area.setEnabled(True)
        self.render_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def onAbort(self):
        assert self._renderer is not None
        self._renderer.abort()


class Renderer(QtCore.QObject):
    progress = QtCore.pyqtSignal(int)
    done = QtCore.pyqtSignal()

    ABORTED = 'aborted'
    SUCCESS = 'success'
    FAILED = 'failed'

    def __init__(self, project, path, file_format):
        super().__init__()

        self.project = project
        self.path = path
        self.file_format = file_format

        self._status = None
        self._reason = None
        self._thread = None
        self._aborted = threading.Event()

    @property
    def status(self):
        return self._status

    @property
    def reason(self):
        return self._reason or "Unknown error"

    def start(self):
        assert self._thread is None
        self._thread = threading.Thread(target=self._render)
        self._thread.start()

    def abort(self):
        self._aborted.set()

    def _render(self):
        try:
            total_samples = self.project.property_track.get_num_samples(44100)

            raise NotImplementedError

            # sink = EncoderSink(self.file_format, self.path)
            # pipeline.set_sink(sink)
            # sink.inputs['in'].connect(project_mixer.outputs['out'])
            # sink.setup()
            # sink.start()
            # try:
            #     self.progress.emit(0)
            #     last_update = time.time()
            #     while True:
            #         if self._aborted.is_set():
            #             logger.info("Aborted.")
            #             self._status = self.ABORTED
            #             return

            #         try:
            #             num_samples = sink.consume()
            #         except EndOfStreamError:
            #             logger.info("End of stream reached.")
            #             break

            #         now = time.time()
            #         if now - last_update > 0.1:
            #             self.progress.emit(
            #                 min(100, int(100 * num_samples / total_samples)))
            #             last_update = now

            # finally:
            #     logger.info("Cleaning up nodes...")
            #     for node in reversed(pipeline.sorted_nodes):
            #         node.stop()
            #         node.cleanup()

            self._status = self.SUCCESS

        except Exception as exc:
            logger.exception("Project renderer failed with an exception:")
            self._status = self.FAILED
            self._reason = str(exc)

        finally:
            self.done.emit()


