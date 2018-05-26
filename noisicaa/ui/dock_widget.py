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
from typing import Any, Union

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import ui_base

logger = logging.getLogger(__name__)


class DockWidget(ui_base.CommonMixin, QtWidgets.QDockWidget):
    def __init__(
            self, title: str, identifier: str,
            allowed_areas: Union[Qt.DockWidgetAreas, Qt.DockWidgetArea] = Qt.AllDockWidgetAreas,
            initial_area: QtCore.Qt.DockWidgetArea = Qt.RightDockWidgetArea,
            initial_visible: bool = False,
            initial_floating: bool = False,
            initial_pos: QtCore.QPoint = None,
            **kwargs: Any) -> None:
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

        name = QtWidgets.QLabel(self)
        name.setTextFormat(Qt.PlainText)
        name.setText(self.windowTitle())
        #self.windowTitleChanged.connect(name.setText)

        self.hide_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('list-remove'),
            autoRaise=True,
            focusPolicy=Qt.NoFocus)
        self.hide_button.clicked.connect(self.toggleHide)

        self.float_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('view-fullscreen'),
            checkable=True,
            autoRaise=True,
            focusPolicy=Qt.NoFocus)
        self.float_button.toggled.connect(self.setFloating)

        self.close_button = QtWidgets.QToolButton(
            icon=QtGui.QIcon.fromTheme('window-close'),
            autoRaise=True,
            focusPolicy=Qt.NoFocus)
        self.close_button.clicked.connect(lambda: self.setVisible(False))

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.addWidget(self.hide_button)
        layout.addWidget(name, 1)
        layout.addWidget(self.float_button)
        layout.addWidget(self.close_button)

        self.titlebar = QtWidgets.QWidget(self)
        self.titlebar.setLayout(layout)
        self.setTitleBarWidget(self.titlebar)

        self.onFeaturesChanged(self.features())
        self.featuresChanged.connect(self.onFeaturesChanged)
        self.onTopLevelChanged(self.isFloating())
        self.topLevelChanged.connect(self.onTopLevelChanged)

        self.main_widget = None  # type: QtWidgets.QWidget
        self.filler = QtWidgets.QWidget(self)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        self.main_layout.addWidget(self.filler)

        top_widget = QtWidgets.QWidget(self)
        top_widget.setLayout(self.main_layout)
        super().setWidget(top_widget)

    def setWidget(self, widget: QtWidgets.QWidget) -> None:
        if self.main_widget is not None:
            self.main_widget.setParent(None)
            self.main_layout.removeWidget(self.main_widget)

        if self.widget is not None:
            self.main_layout.addWidget(widget)
            self.filler.setMaximumHeight(0)
            self.filler.hide()

        self.main_widget = widget

    def onTopLevelChanged(self, top_level: bool) -> None:
        self.hide_button.setDisabled(top_level)
        self.float_button.setChecked(top_level)
        if top_level:
            if self.widget() is not None:
                self.widget().show()
            self.hide_button.setIcon(QtGui.QIcon.fromTheme('list-remove'))

    def onFeaturesChanged(self, features: QtWidgets.QDockWidget.DockWidgetFeatures) -> None:
        self.float_button.setVisible(features & QtWidgets.QDockWidget.DockWidgetFloatable != 0)
        self.close_button.setVisible(features & QtWidgets.QDockWidget.DockWidgetClosable != 0)

    def toggleHide(self) -> None:
        if self.main_widget.isHidden():
            self.filler.hide()
            self.main_widget.show()
            self.hide_button.setIcon(QtGui.QIcon.fromTheme('list-remove'))
        else:
            self.main_widget.hide()
            self.filler.show()
            self.hide_button.setIcon(QtGui.QIcon.fromTheme('list-add'))
