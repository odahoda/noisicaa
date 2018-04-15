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

# mypy: loose

import asyncio
import enum
import logging
import os.path

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.core import ipc
from . import ui_base
from . import qprogressindicator

logger = logging.getLogger(__name__)


class State(enum.Enum):
    IDLE = 'idle'
    SETUP = 'setup'
    RUNNING = 'running'
    CLEANUP = 'cleanup'
    ABORTING = 'aborting'
    DONE = 'done'


suffix_map = {
    music.RenderSettings.FLAC: '.flac',
    music.RenderSettings.OGG: '.ogg',
    music.RenderSettings.WAVE: '.wav',
    music.RenderSettings.MP3: '.mp3',
}


def populateComboBox(widget, values, current):
    for idx, (label, value) in enumerate(values):
        widget.addItem(label, userData=value)
        if value == current:
            widget.setCurrentIndex(idx)


class QValueSlider(QtWidgets.QWidget):
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)

        self.__fmt = '%d'
        self.__translate = lambda x: x

        self.__slider = QtWidgets.QSlider(self)
        self.__slider.setOrientation(Qt.Horizontal)
        self.__slider.valueChanged.connect(self.__onValueChanged)

        self.__label = QtWidgets.QLabel(self)
        self.__label.setAlignment(Qt.AlignRight)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.__slider, 1)
        layout.addWidget(self.__label)
        self.setLayout(layout)

        self.__update()

    def __formatValue(self, value):
        return self.__fmt % self.__translate(value)

    def __update(self):
        self.__label.setText(self.__formatValue(self.value()))

        font_metrics = self.__label.fontMetrics()
        self.__label.setMinimumWidth(10 + max(
            font_metrics.boundingRect(self.__formatValue(value)).width()
            for value in [self.__slider.minimum(), self.__slider.maximum()]))

    def setRange(self, minimum, maximum):
        self.__slider.setRange(minimum, maximum)
        self.__update()

    def setValue(self, value):
        self.__slider.setValue(value)

    def value(self):
        return self.__slider.value()

    def __onValueChanged(self, value):
        self.valueChanged.emit(value)
        self.__label.setText(self.__formatValue(value))

    def setFormat(self, fmt):
        self.__fmt = fmt
        self.__update()

    def setTranslateFunction(self, func):
        self.__translate = func
        self.__update()


class RenderDialog(ui_base.ProjectMixin, QtWidgets.QDialog):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # TODO: persist
        path = '/tmp/test.flac'
        self.__settings = music.RenderSettings()

        self.__aborted = asyncio.Event(loop=self.event_loop)
        self.__cb_server = None
        self.__out_fp = None
        self.__bytes_written = None
        self.__renderer_state = None
        self.__failure_reason = None

        self.setWindowTitle("noisicaä - Render Project")
        self.setMinimumWidth(500)

        self.top_area = QtWidgets.QWidget(self)

        self.select_output_directory = QtWidgets.QToolButton(
            self.top_area,
            icon=QtGui.QIcon.fromTheme('document-open'),
            autoRaise=True)
        self.select_output_directory.clicked.connect(self.onSelectOutputDirectory)

        self.output_directory = QtWidgets.QLineEdit(self.top_area)
        self.output_directory.setText(os.path.dirname(path))
        self.output_directory.textChanged.connect(lambda _: self.validateOutputDirectory())

        self.output_directory_warning = QtWidgets.QLabel(self)
        self.output_directory_warning.setPixmap(
            QtGui.QIcon.fromTheme('dialog-warning').pixmap(24, 24))

        self.file_name = QtWidgets.QLineEdit(self.top_area)
        self.file_name.setText(os.path.basename(path))
        self.file_name.textChanged.connect(lambda _: self.validateFileName())

        self.file_name_warning = QtWidgets.QLabel(self)
        self.file_name_warning.setPixmap(QtGui.QIcon.fromTheme('dialog-warning').pixmap(24, 24))

        self.block_size = QtWidgets.QComboBox(self.top_area)
        populateComboBox(
            self.block_size,
            [("%d" % (2 ** e), 2 ** e) for e in range(5, 16)],
            self.__settings.block_size)
        self.block_size.currentIndexChanged.connect(self.onBlockSizeChanged)

        self.sample_rate = QtWidgets.QComboBox(self.top_area)
        populateComboBox(
            self.sample_rate,
            [("22.05 kHz", 22050),
             ("44.1 kHz", 44100),
             ("48 kHz", 48000),
             ("96 kHz", 96000),
            ],
            self.__settings.sample_rate)
        self.sample_rate.currentIndexChanged.connect(self.onSampleRateChanged)

        self.output_format = QtWidgets.QComboBox(self.top_area)
        populateComboBox(
            self.output_format,
            [("FLAC", music.RenderSettings.FLAC),
             ("Ogg", music.RenderSettings.OGG),
             ("MP3", music.RenderSettings.MP3),
             ("Wave", music.RenderSettings.WAVE),
            ],
            self.__settings.output_format)
        self.output_format.currentIndexChanged.connect(self.onOutputFormatChanged)

        flac_settings = QtWidgets.QGroupBox(self.top_area)
        flac_settings.setTitle("FLAC encoder settings")
        flac_settings.setAlignment(Qt.AlignLeft)

        self.flac_bits_per_sample = QtWidgets.QComboBox(flac_settings)
        populateComboBox(
            self.flac_bits_per_sample,
            [("16", 16),
             ("24", 24),
            ],
            self.__settings.flac_settings.bits_per_sample)
        self.flac_bits_per_sample.currentIndexChanged.connect(self.onFlacBitsPerSampleChanged)

        self.flac_compression_level = QValueSlider(flac_settings)
        self.flac_compression_level.setRange(0, 12)
        self.flac_compression_level.setValue(self.__settings.flac_settings.compression_level)
        self.flac_compression_level.valueChanged.connect(self.onFlacCompressionLevelChanged)

        ogg_settings = QtWidgets.QGroupBox(self.top_area)
        ogg_settings.setTitle("Ogg encoder settings")

        self.ogg_encode_mode = QtWidgets.QComboBox(ogg_settings)
        populateComboBox(
            self.ogg_encode_mode,
            [("Variable bitrate", music.RenderSettings.OggSettings.VBR),
             ("Constant bitrate", music.RenderSettings.OggSettings.CBR),
            ],
            self.__settings.ogg_settings.encode_mode)
        self.ogg_encode_mode.currentIndexChanged.connect(self.onOggEncodeModeChanged)

        self.ogg_bitrate = QValueSlider(ogg_settings)
        self.ogg_bitrate.setFormat('%d kbit/s')
        self.ogg_bitrate.setRange(45, 500)
        self.ogg_bitrate.setValue(self.__settings.ogg_settings.bitrate)
        self.ogg_bitrate.valueChanged.connect(self.onOggBitrateChanged)

        self.ogg_quality = QValueSlider(ogg_settings)
        self.ogg_quality.setFormat('%.1f')
        self.ogg_quality.setTranslateFunction(lambda x: float(x) / 10)
        self.ogg_quality.setRange(-10, 100)
        self.ogg_quality.setValue(int(10 * self.__settings.ogg_settings.quality))
        self.ogg_quality.valueChanged.connect(self.onOggQualityChanged)

        wave_settings = QtWidgets.QGroupBox(self.top_area)
        wave_settings.setTitle("Wave encoder settings")

        self.wave_bits_per_sample = QtWidgets.QComboBox(wave_settings)
        populateComboBox(
            self.wave_bits_per_sample,
            [("16", 16),
             ("24", 24),
             ("32", 32),
            ],
            self.__settings.wave_settings.bits_per_sample)
        self.wave_bits_per_sample.currentIndexChanged.connect(self.onWaveBitsPerSampleChanged)

        mp3_settings = QtWidgets.QGroupBox(self.top_area)
        mp3_settings.setTitle("MP3 encoder settings")

        self.mp3_encode_mode = QtWidgets.QComboBox(mp3_settings)
        populateComboBox(
            self.mp3_encode_mode,
            [("Variable bitrate", music.RenderSettings.Mp3Settings.VBR),
             ("Constant bitrate", music.RenderSettings.Mp3Settings.CBR),
            ],
            self.__settings.mp3_settings.encode_mode)
        self.mp3_encode_mode.currentIndexChanged.connect(self.onMp3EncodeModeChanged)

        self.mp3_bitrate = QValueSlider(mp3_settings)
        self.mp3_bitrate.setFormat('%d kbit/s')
        self.mp3_bitrate.setRange(32, 320)
        self.mp3_bitrate.setValue(self.__settings.mp3_settings.bitrate)
        self.mp3_bitrate.valueChanged.connect(self.onMp3BitrateChanged)

        self.mp3_compression_level = QValueSlider(mp3_settings)
        self.mp3_compression_level.setRange(0, 9)
        self.mp3_compression_level.setValue(self.__settings.mp3_settings.compression_level)
        self.mp3_compression_level.valueChanged.connect(self.onMp3CompressionLevelChanged)

        self.format_settings = {
            music.RenderSettings.FLAC: flac_settings,
            music.RenderSettings.OGG: ogg_settings,
            music.RenderSettings.WAVE: wave_settings,
            music.RenderSettings.MP3: mp3_settings,
        }

        self.progress = QtWidgets.QProgressBar(self.top_area)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.progress.setMinimumWidth(200)

        self.status = QtWidgets.QLabel(self)
        self.status.setVisible(False)
        font = QtGui.QFont(self.status.font())
        font.setWeight(QtGui.QFont.Bold)
        if font.pixelSize() != -1:
            font.setPixelSize(14 * font.pixelSize() // 10)
        else:
            font.setPointSizeF(1.4 * font.pointSizeF())
        self.status.setFont(font)

        self.spinner = QtWidgets.QWidget(self)
        spinner_indicator = qprogressindicator.QProgressIndicator(self.spinner)
        spinner_indicator.setAnimationDelay(100)
        spinner_indicator.startAnimation()

        self.spinner_label = QtWidgets.QLabel(self.spinner)
        self.spinner_label.setAlignment(Qt.AlignVCenter)

        spinner_layout = QtWidgets.QHBoxLayout()
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        spinner_layout.addWidget(spinner_indicator)
        spinner_layout.addWidget(self.spinner_label)
        self.spinner.setLayout(spinner_layout)

        self.abort_button = QtWidgets.QPushButton("Abort")
        self.abort_button.setVisible(False)
        self.abort_button.clicked.connect(self.onAbort)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        self.render_button = QtWidgets.QPushButton("Render")
        self.render_button.clicked.connect(self.onRender)

        output_directory_layout = QtWidgets.QHBoxLayout()
        output_directory_layout.setSpacing(1)
        output_directory_layout.addWidget(self.output_directory, 1)
        output_directory_layout.addWidget(self.select_output_directory)
        output_directory_layout.addWidget(self.output_directory_warning)

        file_name_layout = QtWidgets.QHBoxLayout()
        file_name_layout.setSpacing(1)
        file_name_layout.addWidget(self.file_name, 1)
        file_name_layout.addWidget(self.file_name_warning)

        path_layout = QtWidgets.QFormLayout()
        path_layout.addRow("Output Directory", output_directory_layout)
        path_layout.addRow("Filename", file_name_layout)

        pipeline_layout = QtWidgets.QHBoxLayout()
        pipeline_layout.addWidget(QtWidgets.QLabel("Block size"))
        pipeline_layout.addWidget(self.block_size, 1)
        pipeline_layout.addSpacing(20)
        pipeline_layout.addWidget(QtWidgets.QLabel("Sample rate"))
        pipeline_layout.addWidget(self.sample_rate, 1)

        format_layout = QtWidgets.QHBoxLayout()
        format_layout.addWidget(QtWidgets.QLabel("Format"))
        format_layout.addWidget(self.output_format, 1)

        flac_settings_layout = QtWidgets.QFormLayout()
        flac_settings_layout.addRow("Bits per sample", self.flac_bits_per_sample)
        flac_settings_layout.addRow("Compression level", self.flac_compression_level)
        flac_settings.setLayout(flac_settings_layout)

        ogg_settings_layout = QtWidgets.QFormLayout()
        ogg_settings_layout.addRow("Mode", self.ogg_encode_mode)
        ogg_settings_layout.addRow("Bitrate", self.ogg_bitrate)
        ogg_settings_layout.addRow("Quality", self.ogg_quality)
        ogg_settings.setLayout(ogg_settings_layout)

        wave_settings_layout = QtWidgets.QFormLayout()
        wave_settings_layout.addRow("Bits per sample", self.wave_bits_per_sample)
        wave_settings.setLayout(wave_settings_layout)

        mp3_settings_layout = QtWidgets.QFormLayout()
        mp3_settings_layout.addRow("Mode", self.mp3_encode_mode)
        mp3_settings_layout.addRow("Bitrate", self.mp3_bitrate)
        mp3_settings_layout.addRow("Compression level", self.mp3_compression_level)
        mp3_settings.setLayout(mp3_settings_layout)

        top_layout = QtWidgets.QVBoxLayout()
        top_layout.addLayout(path_layout)
        top_layout.addLayout(pipeline_layout)
        top_layout.addLayout(format_layout)
        top_layout.addWidget(flac_settings)
        top_layout.addWidget(ogg_settings)
        top_layout.addWidget(wave_settings)
        top_layout.addWidget(mp3_settings)
        top_layout.addStretch(1)
        self.top_area.setLayout(top_layout)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.progress)
        buttons.addWidget(self.status)
        buttons.addWidget(self.spinner)
        buttons.addStretch(1)
        buttons.addWidget(self.abort_button)
        buttons.addWidget(self.render_button)
        buttons.addWidget(self.close_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.top_area, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.validateOutputDirectory()
        self.validateFileName()
        self.onOutputFormatChanged()
        self.onOggEncodeModeChanged()
        self.onMp3EncodeModeChanged()

        self.__ui_state = State.IDLE
        self.top_area.setEnabled(True)

        self.abort_button.setVisible(False)
        self.render_button.setEnabled(True)
        self.close_button.setEnabled(True)

        self.progress.setVisible(False)
        self.status.setVisible(False)
        self.spinner.setVisible(False)

    def setUIState(self, state):
        assert isinstance(state, State)
        assert state != State.IDLE

        if state == self.__ui_state:
            return

        valid_transitions = {
            State.IDLE: [State.SETUP],
            State.SETUP: [State.RUNNING, State.ABORTING, State.DONE],
            State.RUNNING: [State.CLEANUP, State.ABORTING, State.DONE],
            State.CLEANUP: [State.DONE],
            State.ABORTING: [State.DONE],
            State.DONE: [State.SETUP],
        }
        assert state in valid_transitions[self.__ui_state], (
            "Invalid transition %s->%s" % (self.__ui_state, state))

        method = {
            State.SETUP: self.__uiStateSetup,
            State.RUNNING: self.__uiStateRunning,
            State.CLEANUP: self.__uiStateCleanup,
            State.ABORTING: self.__uiStateAborting,
            State.DONE: self.__uiStateDone,
        }[state]
        method()
        self.__ui_state = state

    def __uiStateSetup(self):
        self.top_area.setEnabled(False)

        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.render_button.setEnabled(False)
        self.close_button.setEnabled(False)

        self.progress.setVisible(False)
        self.status.setVisible(False)
        self.spinner.setVisible(True)
        self.spinner_label.setText("Setting up pipeline...")

    def __uiStateRunning(self):
        self.top_area.setEnabled(False)

        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.render_button.setEnabled(False)
        self.close_button.setEnabled(False)

        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setVisible(False)
        self.spinner.setVisible(False)

    def __uiStateCleanup(self):
        self.top_area.setEnabled(False)

        self.abort_button.setVisible(False)
        self.render_button.setEnabled(False)
        self.close_button.setEnabled(False)

        self.progress.setVisible(False)
        self.status.setVisible(False)
        self.spinner.setVisible(True)
        self.spinner_label.setText("Tearning down pipeline...")

    def __uiStateAborting(self):
        self.top_area.setEnabled(False)

        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(False)
        self.render_button.setEnabled(False)
        self.close_button.setEnabled(False)

        self.progress.setVisible(False)
        self.status.setVisible(False)
        self.spinner.setVisible(True)
        self.spinner_label.setText("Aborting...")

    def __uiStateDone(self):
        self.top_area.setEnabled(True)

        self.abort_button.setVisible(False)
        self.render_button.setEnabled(True)
        self.close_button.setEnabled(True)

        self.progress.setVisible(False)
        self.status.setVisible(True)
        self.spinner.setVisible(False)

    def setStatusMessage(self, msg, color):
        self.status.setText(msg)
        palette = QtGui.QPalette(self.status.palette())
        palette.setColor(QtGui.QPalette.WindowText, color)
        self.status.setPalette(palette)

    def getOutputDirectoryError(self):
        directory = self.output_directory.text()

        if not directory:
            return "You must set the directory."

        if not os.path.isdir(directory):
            return "This is not an existing directory."

        return None

    def getFileNameError(self):
        filename = self.file_name.text()

        if not filename:
            return "You must set the filename."

        if len(filename) > 255:
            return "Filename is too long."

        if filename in ('.', '..'):
            return "'%s' is not a valid filename." % filename

        if '/' in filename:
            return "Invalid character '/' in filename."

        if '\000' in filename:
            return "Invalid character '\\000' in filename."

        return None

    def isPathValid(self):
        return self.getOutputDirectoryError() is None and self.getFileNameError() is None

    def validateOutputDirectory(self):
        err = self.getOutputDirectoryError()
        self.output_directory_warning.setVisible(err is not None)
        self.output_directory_warning.setToolTip(err)
        self.render_button.setEnabled(self.isPathValid())

    def validateFileName(self):
        err = self.getFileNameError()
        self.file_name_warning.setVisible(err is not None)
        self.file_name_warning.setToolTip(err)
        self.render_button.setEnabled(self.isPathValid())

    def onSelectOutputDirectory(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption="Select output directory...",
            directory=self.output_directory.text())
        if path is not None:
            self.output_directory.setText(path)

    def onBlockSizeChanged(self):
        self.__settings.block_size = self.block_size.currentData()

    def onSampleRateChanged(self):
        self.__settings.sample_rate = self.sample_rate.currentData()

    def onOutputFormatChanged(self):
        output_format = self.output_format.currentData()
        self.__settings.output_format = output_format

        # First hide all group boxes, then show the current one.
        # If we show/hide in a single passm then there could be cases, where there are two
        # shown at once (even if one will be hidden again immediately) and the layout gets
        # recomputed to have space for both - which will then be filled with space.
        for fmt, grp in self.format_settings.items():
            grp.hide()

        for fmt, grp in self.format_settings.items():
            if fmt == output_format:
                grp.show()

        suffix = suffix_map[output_format]
        file_name = self.file_name.text()
        old_suffix = os.path.splitext(file_name)[1]
        if old_suffix and old_suffix in suffix_map.values():
            file_name = file_name[:-len(old_suffix)]
            file_name += suffix
        self.file_name.setText(file_name)

    def onFlacBitsPerSampleChanged(self):
        self.__settings.flac_settings.bits_per_sample = self.flac_bits_per_sample.currentData()

    def onFlacCompressionLevelChanged(self):
        self.__settings.flac_settings.compression_level = self.flac_compression_level.value()

    def onOggEncodeModeChanged(self):
        self.__settings.ogg_settings.encode_mode = self.ogg_encode_mode.currentData()
        self.ogg_bitrate.setEnabled(
            self.__settings.ogg_settings.encode_mode == music.RenderSettings.OggSettings.CBR)
        self.ogg_quality.setEnabled(
            self.__settings.ogg_settings.encode_mode == music.RenderSettings.OggSettings.VBR)

    def onOggBitrateChanged(self):
        self.__settings.ogg_settings.bitrate = self.ogg_bitrate.value()

    def onOggQualityChanged(self):
        self.__settings.ogg_settings.quality = float(self.ogg_quality.value()) / 10.0

    def onWaveBitsPerSampleChanged(self):
        self.__settings.wave_settings.bits_per_sample = self.wave_bits_per_sample.currentData()

    def onMp3EncodeModeChanged(self):
        self.__settings.mp3_settings.encode_mode = self.mp3_encode_mode.currentData()
        self.mp3_bitrate.setEnabled(
            self.__settings.mp3_settings.encode_mode == music.RenderSettings.Mp3Settings.CBR)
        self.mp3_compression_level.setEnabled(
            self.__settings.mp3_settings.encode_mode == music.RenderSettings.Mp3Settings.VBR)

    def onMp3BitrateChanged(self):
        self.__settings.mp3_settings.bitrate = self.mp3_bitrate.value()

    def onMp3CompressionLevelChanged(self):
        self.__settings.mp3_settings.compression_level = self.mp3_compression_level.value()

    def onAbort(self):
        self.__aborted.set()

        self.setUIState(State.ABORTING)

    def onRender(self):
        path = os.path.join(self.output_directory.text(), self.file_name.text())

        if os.path.exists(path):
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Overwrite file?")
            msg.setText("The file \"%s\" already exists.\nDo you want to overwrite it?" % path)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.addButton("Overwrite", QtWidgets.QMessageBox.AcceptRole)
            msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
            msg.exec_()

            if msg.buttonRole(msg.clickedButton()) == QtWidgets.QMessageBox.RejectRole:
                return

        self.__bytes_written = 0
        self.__renderer_state = None
        self.__failure_reason = None
        self.__aborted.clear()
        self.call_async(self.__runRenderer(path), self.onRendererDone)

        self.setUIState(State.SETUP)

    def onRendererDone(self, _):
        if self.__renderer_state == 'complete':
            self.setStatusMessage("Done.", QtGui.QColor(60, 160, 60))

        else:
            assert self.__renderer_state == 'failed'
            if self.__aborted.is_set():
                self.setStatusMessage("Aborted", QtGui.QColor(255, 60, 60))

            elif self.__failure_reason is not None:
                self.setStatusMessage("Failed!", QtGui.QColor(255, 60, 60))

                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle("Renderer failed")
                msg.setText("Rendering failed with an error:")
                msg.setInformativeText(self.__failure_reason)
                msg.setIcon(QtWidgets.QMessageBox.Critical)
                msg.addButton("Ok", QtWidgets.QMessageBox.AcceptRole)
                msg.exec_()

            else:
                self.setStatusMessage("Failed! (unknown reason)", QtGui.QColor(255, 60, 60))

        self.setUIState(State.DONE)

    def __onRendererState(self, state):
        self.__renderer_state = state

        if state == 'setup':
            self.setUIState(State.SETUP)
        elif state == 'render':
            self.setUIState(State.RUNNING)
        elif state == 'cleanup':
            self.setUIState(State.CLEANUP)

    def __onRendererProgress(self, progress):
        self.progress.setValue(int(100 * progress))
        return self.__aborted.is_set()

    def __onRendererData(self, data):
        try:
            self.__out_fp.write(data)
        except (IOError, OSError) as exc:
            return False, str(exc)

        self.__bytes_written += len(data)
        return True, ""

    async def __runRenderer(self, path):
        tmp_path = path + '.partial'
        try:
            self.__out_fp = open(tmp_path, 'wb')

            self.__cb_server = ipc.Server(
                self.event_loop, 'render_cb', socket_dir=self.app.process.tmp_dir)
            self.__cb_server.add_command_handler('STATE', self.__onRendererState)
            self.__cb_server.add_command_handler('PROGRESS', self.__onRendererProgress)
            self.__cb_server.add_command_handler(
                'DATA', self.__onRendererData, log_level=logging.DEBUG)
            await self.__cb_server.setup()

            await self.project_client.render(self.__cb_server.address, self.__settings)

            assert self.__renderer_state is not None

            self.__out_fp.close()
            self.__out_fp = None

            if os.path.exists(path):
                os.unlink(path)
            os.rename(tmp_path, path)

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Project renderer failed with an exception:")
            self.__renderer_state = 'failed'
            self.__failure_reason = str(exc)

        finally:
            if self.__cb_server is not None:
                await self.__cb_server.cleanup()
                self.__cb_server = None

            if self.__out_fp is not None:
                self.__out_fp.close()
                self.__out_fp = None

            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
