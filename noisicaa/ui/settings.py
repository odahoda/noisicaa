#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import os.path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants import DATA_DIR

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self._app = parent._app

        self.setWindowTitle("noisicaä - Settings")

        self.tabs = QTabWidget(self)

        for cls in (AppearancePage, AudioPage):
            page = cls(self)
            self.tabs.addTab(page, page.getIcon(), page.title)

        close = QPushButton("Close")
        close.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout()
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.setVisible(
            int(self._app.settings.value(
                'dialog/settings/visible', False)))
        self.restoreGeometry(
            self._app.settings.value(
                'dialog/settings/geometry', b''))
        self.tabs.setCurrentIndex(
            int(self._app.settings.value('dialog/settings/page', 0)))

    def storeState(self):
        s = self._app.settings
        s.beginGroup('dialog/settings')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.setValue('page', self.tabs.currentIndex())
        s.endGroup()


class Page(QWidget):
    def __init__(self, parent):
        super().__init__()

        self._app = parent._app

        layout = QVBoxLayout()

        self.createOptions(layout)

        layout.addStretch(1)
        self.setLayout(layout)


class AppearancePage(Page):
    def __init__(self, parent):
        self.title = "Appearance"
        self._qt_styles = sorted(QStyleFactory.keys())

        super().__init__(parent)

    def getIcon(self):
        path = os.path.join(DATA_DIR, 'icons', 'settings_appearance.png')
        return QIcon(path)

    def createOptions(self, layout):
        self.createQtStyle(layout)

    def createQtStyle(self, parent):
        layout = QHBoxLayout()
        parent.addLayout(layout)

        label = QLabel("Qt Style:")
        layout.addWidget(label)

        combo = QComboBox()
        layout.addWidget(combo)

        current = self._app.settings.value(
            'appearance/qtStyle', self._app.default_style)
        for index, style in enumerate(self._qt_styles):
            if style.lower() == self._app.default_style.lower():
                style += " (default)"
            combo.addItem(style)
            if style.lower() == current.lower():
                combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(self.qtStyleChanged)

    def qtStyleChanged(self, index):
        style_name = self._qt_styles[index]
        style = QStyleFactory.create(style_name)
        self._app.setStyle(style)

        self._app.settings.setValue('appearance/qtStyle', style_name)



class AudioPage(Page):
    def __init__(self, parent=None):
        self.title = "Audio"
        super().__init__(parent)


    def getIcon(self):
        path = os.path.join(DATA_DIR, 'icons', 'settings_audio.png')
        return QIcon(path)

    def createOptions(self, layout):
        pass
