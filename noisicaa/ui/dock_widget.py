#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt, QSize, QMargins
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDockWidget, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QLayout

from . import ui_base

logger = logging.getLogger(__name__)


class DockWidget(ui_base.CommonMixin, QDockWidget):
    def __init__(self, title, identifier,
                 allowed_areas=Qt.AllDockWidgetAreas,
                 initial_area=Qt.RightDockWidgetArea,
                 initial_visible=False,
                 initial_floating=False,
                 initial_pos=False,
                 **kwargs):
        super().__init__(**kwargs)
        self._identifier = identifier

        self.setWindowTitle(title)
        self.setObjectName('dock:' + identifier)
        self.setAllowedAreas(allowed_areas)
        self.parent().addDockWidget(initial_area, self)
        self.setVisible(initial_visible)
        self.setFloating(initial_floating)
        if initial_floating and initial_pos is not None:
            self.move(initial_pos)

        self.parent()._view_menu.addAction(self.toggleViewAction())

        name = QLabel(self, textFormat=Qt.PlainText)
        name.setText(self.windowTitle())
        #self.windowTitleChanged.connect(name.setText)

        self.hide_button = QToolButton(
            icon=QIcon.fromTheme('list-remove'),
            autoRaise=True,
            focusPolicy=Qt.NoFocus)
        self.hide_button.clicked.connect(self.toggleHide)

        self.float_button = QToolButton(
            icon=QIcon.fromTheme('view-fullscreen'),
            checkable=True,
            autoRaise=True,
            focusPolicy=Qt.NoFocus)
        self.float_button.toggled.connect(self.setFloating)

        self.close_button = QToolButton(
            icon=QIcon.fromTheme('window-close'),
            autoRaise=True,
            focusPolicy=Qt.NoFocus)
        self.close_button.clicked.connect(lambda: self.setVisible(False))

        layout = QHBoxLayout()
        layout.setContentsMargins(QMargins(0, 0, 0, 0))
        layout.addWidget(self.hide_button)
        layout.addWidget(name, 1)
        layout.addWidget(self.float_button)
        layout.addWidget(self.close_button)

        self.titlebar = QWidget(self)
        self.titlebar.setLayout(layout)
        self.setTitleBarWidget(self.titlebar)

        self.onFeaturesChanged(self.features())
        self.featuresChanged.connect(self.onFeaturesChanged)
        self.onTopLevelChanged(self.isFloating())
        self.topLevelChanged.connect(self.onTopLevelChanged)

        self.main_widget = None
        self.filler = QWidget(self)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        self.main_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.main_layout.addWidget(self.filler)

        top_widget = QWidget(self)
        top_widget.setLayout(self.main_layout)
        super().setWidget(top_widget)

    def setWidget(self, widget):
        if self.main_widget is None:
            self.main_layout.removeWidget(self.main_widget)

        if self.widget is not None:
            self.main_layout.addWidget(widget)
            self.filler.setMaximumHeight(0)
            self.filler.hide()

        self.main_widget = widget

    def onTopLevelChanged(self, top_level):
        self.hide_button.setDisabled(top_level)
        if top_level:
            if self.widget() is not None:
                self.widget().show()
            self.hide_button.setIcon(QIcon.fromTheme('list-remove'))

    def onFeaturesChanged(self, features):
        self.float_button.setVisible(
            features & QDockWidget.DockWidgetFloatable != 0)
        self.close_button.setVisible(
            features & QDockWidget.DockWidgetClosable != 0)

    def toggleHide(self):
        if self.main_widget.isHidden():
            self.filler.hide()
            self.main_widget.show()
            self.hide_button.setIcon(QIcon.fromTheme('list-remove'))
        else:
            self.main_widget.hide()
            self.filler.show()
            self.hide_button.setIcon(QIcon.fromTheme('list-add'))
