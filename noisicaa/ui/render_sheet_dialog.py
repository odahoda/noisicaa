#!/usr/bin/python3

import logging
import os.path
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialog,
    QToolButton,
    QFileDialog,
    QComboBox,
    QProgressBar,
    QLabel,
)

logger = logging.getLogger(__name__)


class RenderSheetDialog(QDialog):
    def __init__(self, parent, app, sheet):
        super().__init__(parent)

        self._app = app
        self._sheet = sheet

        self._file_name_suffix = '.flac'

        self._renderer = None

        self.setWindowTitle("noisicaä - Render Sheet")

        self.top_area = QWidget(self)

        self.select_output_directory = QToolButton(
            self.top_area,
            icon=QIcon.fromTheme('document-open'),
            autoRaise=True)
        self.select_output_directory.clicked.connect(self.onSelectOutputDirectory)

        self.output_directory = QLineEdit(self.top_area, text="/tmp")

        self.file_name = QLineEdit(self.top_area, text="test.flac")

        self.file_format = QComboBox(self.top_area)
        self.file_format.addItem("FLAC", userData="flac")
        self.file_format.addItem("OGG", userData="ogg")
        self.file_format.currentIndexChanged.connect(self.onFileFormatChanged)

        self.progress = QProgressBar(
            self.top_area, minimum=0, maximum=100, visible=False)
        self.progress.setMinimumWidth(200)

        self.status = QLabel(self, visible=False)
        font = QFont(self.status.font())
        font.setWeight(QFont.Bold)
        if font.pixelSize() != -1:
            font.setPixelSize(14 * font.pixelSize() // 10)
        else:
            font.setPointSizeF(1.4 * font.pointSizeF())
        self.status.setFont(font)

        self.abort_button = QPushButton("Abort", visible=False)
        self.abort_button.clicked.connect(self.onAbort)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        self.render_button = QPushButton("Render")
        self.render_button.clicked.connect(self.onRender)

        output_directory_layout = QHBoxLayout(spacing=1)
        output_directory_layout.addWidget(self.output_directory, 1)
        output_directory_layout.addWidget(self.select_output_directory)

        top_layout = QFormLayout()
        top_layout.addRow("Output Directory", output_directory_layout)
        top_layout.addRow("Filename", self.file_name)
        top_layout.addRow("Format", self.file_format)

        self.top_area.setLayout(top_layout)

        buttons = QHBoxLayout()
        buttons.addWidget(self.progress)
        buttons.addWidget(self.status)
        buttons.addWidget(self.abort_button)
        buttons.addStretch(1)
        buttons.addWidget(self.render_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout()
        layout.addWidget(self.top_area, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def onSelectOutputDirectory(self):
        path = QFileDialog.getExistingDirectory(
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
            os.path.join(self.output_directory.text(), self.file_name.text()),
            self.file_format.currentData())
        self._renderer.progress.connect(self.progress.setValue)
        self._renderer.done.connect(self.onRendererDone)
        self._renderer.start()

    def onRendererDone(self):
        assert self._renderer is not None

        if self._renderer.status == Renderer.SUCCESS:
            self.status.setText("Done.")
            palette = QPalette(self.status.palette())
            palette.setColor(QPalette.WindowText, QColor(60, 160, 60))
            self.status.setPalette(palette)
        elif self._renderer.status == Renderer.ABORTED:
            self.status.setText("Aborted")
            palette = QPalette(self.status.palette())
            palette.setColor(QPalette.WindowText, QColor(255, 60, 60))
            self.status.setPalette(palette)
        elif self._renderer.status == Renderer.FAILED:
            self.status.setText("Failed!")
            palette = QPalette(self.status.palette())
            palette.setColor(QPalette.WindowText, QColor(255, 60, 60))
            self.status.setPalette(palette)

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


class Renderer(QObject):
    progress = pyqtSignal(int)
    done = pyqtSignal()

    ABORTED = 'aborted'
    SUCCESS = 'success'
    FAILED = 'failed'

    def __init__(self, path, file_format):
        super().__init__()

        self.path = path
        self.file_format = file_format

        self._status = None
        self._thread = None
        self._aborted = threading.Event()

    @property
    def status(self):
        return self._status

    def start(self):
        assert self._thread is None
        self._thread = threading.Thread(target=self._render)
        self._thread.start()

    def abort(self):
        self._aborted.set()

    def _render(self):
        try:
            for p in range(101):
                if self._aborted.is_set():
                    self._status = self.ABORTED
                    return

                self.progress.emit(p)
                time.sleep(0.05)

            self._status = self.SUCCESS
        finally:
            self.done.emit()
