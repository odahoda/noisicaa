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

import functools
import os.path
from typing import Any

from PyQt5 import QtGui
from PyQt5 import QtWidgets

from ..constants import DATA_DIR
from . import ui_base

class SettingsDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setWindowTitle("noisicaä - Settings")
        self.resize(600, 300)

        self.tabs = QtWidgets.QTabWidget(self)

        for cls in (AppearancePage, AudioPage):
            page = cls(context=self.context)
            self.tabs.addTab(page, page.getIcon(), page.title)

        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.setVisible(bool(self.app.settings.value('dialog/settings/visible', False)))
        self.restoreGeometry(self.app.settings.value('dialog/settings/geometry', b''))
        self.tabs.setCurrentIndex(int(self.app.settings.value('dialog/settings/page', 0)))

    def storeState(self) -> None:
        s = self.app.settings
        s.beginGroup('dialog/settings')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.setValue('page', self.tabs.currentIndex())
        s.endGroup()


class Page(ui_base.CommonMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        layout = QtWidgets.QVBoxLayout()

        self.createOptions(layout)

        layout.addStretch(1)
        self.setLayout(layout)


class AppearancePage(Page):
    def __init__(self, **kwargs: Any) -> None:
        self.title = "Appearance"
        self._qt_styles = sorted(QtWidgets.QStyleFactory.keys())

        super().__init__(**kwargs)

    def getIcon(self) -> QtGui.QIcon:
        path = os.path.join(DATA_DIR, 'icons', 'settings_appearance.png')
        return QtGui.QIcon(path)

    def createOptions(self, layout: QtWidgets.QLayout) -> None:
        self.createQtStyle(layout)

    def createQtStyle(self, parent: QtWidgets.QLayout) -> None:
        layout = QtWidgets.QHBoxLayout()
        parent.addLayout(layout)

        label = QtWidgets.QLabel("Qt Style:")
        layout.addWidget(label)

        combo = QtWidgets.QComboBox()
        layout.addWidget(combo)

        current = self.app.settings.value('appearance/qtStyle', self.app.default_style)
        for index, style in enumerate(self._qt_styles):
            if style.lower() == self.app.default_style.lower():
                style += " (default)"
            combo.addItem(style)
            if style.lower() == current.lower():
                combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(self.qtStyleChanged)

    def qtStyleChanged(self, index: int) -> None:
        style_name = self._qt_styles[index]
        style = QtWidgets.QStyleFactory.create(style_name)
        self.app.setStyle(style)

        self.app.settings.setValue('appearance/qtStyle', style_name)


class QBlockSizeSpinBox(QtWidgets.QSpinBox):
    def __init__(self) -> None:
        super().__init__()

        self.lineEdit().setReadOnly(True)
        self.setSuffix(' samples')
        self.setRange(5, 20)
        self.setValue(10)

    def textFromValue(self, value: int) -> str:
        return '%d' % (2**value)


class AudioPage(Page):
    def __init__(self, **kwargs: Any) -> None:
        self.title = "Audio"
        self._backends = ['portaudio', 'null']
        super().__init__(**kwargs)

    def getIcon(self) -> QtGui.QIcon:
        path = os.path.join(DATA_DIR, 'icons', 'settings_audio.png')
        return QtGui.QIcon(path)

    def createOptions(self, layout: QtWidgets.QLayout) -> None:
        backend_widget = QtWidgets.QComboBox()
        #backend_layout.addWidget(combo, stretch=1)

        current = self.app.settings.value('audio/backend', 'portaudio')
        for index, backend in enumerate(self._backends):
            backend_widget.addItem(backend)
            if backend == current:
                backend_widget.setCurrentIndex(index)
        backend_widget.currentIndexChanged.connect(self.backendChanged)

        block_size_widget = QBlockSizeSpinBox()
        block_size_widget.setValue(int(
            self.app.settings.value('audio/block_size', 10)))
        block_size_widget.valueChanged.connect(self.blockSizeChanged)

        sample_rate_widget = QtWidgets.QComboBox()
        for idx, (label, value) in enumerate([("22.05 kHz", 22050),
                                              ("44.1 kHz", 44100),
                                              ("48 kHz", 48000),
                                              ("96 kHz", 96000)]):
            sample_rate_widget.addItem(label, userData=value)
            if value == int(self.app.settings.value('audio/sample_rate', 44100)):
                sample_rate_widget.setCurrentIndex(idx)
        sample_rate_widget.currentIndexChanged.connect(self.sampleRateChanged)

        main_layout = QtWidgets.QFormLayout()
        main_layout.addRow("Backend:", backend_widget)
        main_layout.addRow("Block size:", block_size_widget)
        main_layout.addRow("Sample rate:", sample_rate_widget)

        layout.addLayout(main_layout)

        layout.addStretch()

        buttons_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons_layout)
        buttons_layout.addStretch()

        test_button = QtWidgets.QPushButton("Test")
        buttons_layout.addWidget(test_button)

        test_button.clicked.connect(self.testBackend)

    def backendChanged(self, index: int) -> None:
        backend = self._backends[index]

        self.call_async(
            self.app.audioproc_client.set_backend(backend),
            callback=functools.partial(self._set_backend_done, backend=backend))

    def _set_backend_done(self, result: Any, backend: str) -> None:
        self.app.settings.setValue('audio/backend', backend)

    def blockSizeChanged(self, block_size: int) -> None:
        self.call_async(
            self.app.audioproc_client.set_host_parameters(block_size=2 ** block_size),
            callback=functools.partial(self._set_block_size_done, block_size=block_size))

    def _set_block_size_done(self, result: Any, block_size: int) -> None:
        self.app.settings.setValue('audio/block_size', block_size)

    def sampleRateChanged(self, sample_rate: int) -> None:
        self.call_async(
            self.app.audioproc_client.set_host_parameters(sample_rate=sample_rate),
            callback=functools.partial(self._set_sample_rate_done, sample_rate=sample_rate))

    def _set_sample_rate_done(self, result: Any, sample_rate: int) -> None:
        self.app.settings.setValue('audio/sample_rate', sample_rate)

    def testBackend(self) -> None:
        self.call_async(self._testBackendAsync())

    async def _testBackendAsync(self) -> None:
        await self.app.audioproc_client.play_file(
            os.path.join(DATA_DIR, 'sounds', 'test_sound.wav'))
