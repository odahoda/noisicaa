#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import functools
import math
import os.path

from PyQt5 import QtGui
from PyQt5 import QtWidgets

from ..constants import DATA_DIR
from . import ui_base

class SettingsDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    def __init__(self, app, parent):
        super().__init__(app=app, parent=parent)

        self.setWindowTitle("noisicaä - Settings")
        self.resize(600, 300)

        self.tabs = QtWidgets.QTabWidget(self)

        for cls in (AppearancePage, AudioPage):
            page = cls(self.app)
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

        self.setVisible(
            int(self.app.settings.value(
                'dialog/settings/visible', False)))
        self.restoreGeometry(
            self.app.settings.value(
                'dialog/settings/geometry', b''))
        self.tabs.setCurrentIndex(
            int(self.app.settings.value('dialog/settings/page', 0)))

    def storeState(self):
        s = self.app.settings
        s.beginGroup('dialog/settings')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.setValue('page', self.tabs.currentIndex())
        s.endGroup()


class Page(ui_base.CommonMixin, QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__(app=app)

        layout = QtWidgets.QVBoxLayout()

        self.createOptions(layout)

        layout.addStretch(1)
        self.setLayout(layout)


class AppearancePage(Page):
    def __init__(self, app):
        self.title = "Appearance"
        self._qt_styles = sorted(QtWidgets.QStyleFactory.keys())

        super().__init__(app)

    def getIcon(self):
        path = os.path.join(DATA_DIR, 'icons', 'settings_appearance.png')
        return QtGui.QIcon(path)

    def createOptions(self, layout):
        self.createQtStyle(layout)

    def createQtStyle(self, parent):
        layout = QtWidgets.QHBoxLayout()
        parent.addLayout(layout)

        label = QtWidgets.QLabel("Qt Style:")
        layout.addWidget(label)

        combo = QtWidgets.QComboBox()
        layout.addWidget(combo)

        current = self.app.settings.value(
            'appearance/qtStyle', self.app.default_style)
        for index, style in enumerate(self._qt_styles):
            if style.lower() == self.app.default_style.lower():
                style += " (default)"
            combo.addItem(style)
            if style.lower() == current.lower():
                combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(self.qtStyleChanged)

    def qtStyleChanged(self, index):
        style_name = self._qt_styles[index]
        style = QtWidgets.QStyleFactory.create(style_name)
        self.app.setStyle(style)

        self.app.settings.setValue('appearance/qtStyle', style_name)


class QFrameSizeSpinBox(QtWidgets.QSpinBox):
    def __init__(self):
        super().__init__()

        self.lineEdit().setReadOnly(True)
        self.setSuffix(' samples')
        self.setRange(5, 20)
        self.setValue(10)

    def textFromValue(self, value):
        return '%d' % (2**value)


class AudioPage(Page):
    def __init__(self, app):
        self.title = "Audio"
        self._backends = ['pyaudio', 'null']
        super().__init__(app)

    def getIcon(self):
        path = os.path.join(DATA_DIR, 'icons', 'settings_audio.png')
        return QtGui.QIcon(path)

    def createOptions(self, layout):
        backend_widget = QtWidgets.QComboBox()
        #backend_layout.addWidget(combo, stretch=1)

        current = self.app.settings.value('audio/backend', 'pyaudio')
        for index, backend in enumerate(self._backends):
            backend_widget.addItem(backend)
            if backend == current:
                backend_widget.setCurrentIndex(index)
        backend_widget.currentIndexChanged.connect(self.backendChanged)

        frame_size_widget = QFrameSizeSpinBox()
        frame_size_widget.setValue(int(
            self.app.settings.value('audio/frame_size', 10)))
        frame_size_widget.valueChanged.connect(self.frameSizeChanged)

        main_layout = QtWidgets.QFormLayout()
        main_layout.addRow("Backend:", backend_widget)
        main_layout.addRow("Block size:", frame_size_widget)

        layout.addLayout(main_layout)

        layout.addStretch()

        buttons_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons_layout)
        buttons_layout.addStretch()

        test_button = QtWidgets.QPushButton("Test")
        buttons_layout.addWidget(test_button)

        test_button.clicked.connect(self.testBackend)

    def backendChanged(self, index):
        backend = self._backends[index]

        self.call_async(
            self.app.audioproc_client.set_backend(backend),
            callback=functools.partial(
                self._set_backend_done, backend=backend))

    def _set_backend_done(self, result, backend):
        self.app.settings.setValue('audio/backend', backend)

    def frameSizeChanged(self, frame_size):
        self.call_async(
            self.app.audioproc_client.set_frame_size(2 ** frame_size),
            callback=functools.partial(
                self._set_frame_size_done, frame_size=frame_size))

    def _set_frame_size_done(self, result, frame_size):
        self.app.settings.setValue('audio/frame_size', frame_size)

    def testBackend(self):
        self.call_async(self._testBackendAsync())

    async def _testBackendAsync(self):
        node = await self.app.audioproc_client.play_file(
            '/usr/share/sounds/purple/send.wav')
