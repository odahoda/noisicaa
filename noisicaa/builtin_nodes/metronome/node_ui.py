#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
from typing import Any

from PySide2.QtCore import Qt
from PySide2 import QtGui
from PySide2 import QtWidgets

from noisicaa import constants
from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import property_connector
from noisicaa.ui.graph import base_node
from . import model

logger = logging.getLogger(__name__)


class MetronomeNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, node: model.Metronome, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__sample_path = QtWidgets.QLineEdit()
        self.__sample_path_connector = property_connector.QLineEditConnector[str](
            self.__sample_path, self.__node, 'sample_path',
            mutation_name='%s: Change sample path' % self.__node.name,
            parse_func=str, display_func=str,
            context=self.context)
        self.add_cleanup_function(self.__sample_path_connector.cleanup)

        self.__sample_dialog_action = QtWidgets.QAction("Select sample...", self)
        self.__sample_dialog_action.setIcon(QtGui.QIcon(
            os.path.join(constants.DATA_DIR, 'icons', 'document-open.svg')))
        self.__sample_dialog_action.triggered.connect(self.__showSampleDialog)

        self.__sample_dialog_button = QtWidgets.QToolButton()
        self.__sample_dialog_button.setDefaultAction(self.__sample_dialog_action)

        l1 = QtWidgets.QHBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(QtWidgets.QLabel("Sample:"))
        l1.addWidget(self.__sample_path)
        l1.addWidget(self.__sample_dialog_button)
        self.setLayout(l1)

    def __showSampleDialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self.project_view,
            caption="Select metronome sample",
            directory=os.path.dirname(self.__sample_path.text()),
            filter="All Files (*);;Wav files (*.wav)",
            #initialFilter=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        self.__sample_path.setText(path)
        self.__sample_path.editingFinished.emit()


class MetronomeNode(base_node.Node):
    has_window = True

    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.Metronome), type(node).__name__
        self.__widget = None  # type: QtWidgets.QWidget
        self.__node = node  # type: model.Metronome

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None

        body = MetronomeNodeWidget(
            node=self.__node,
            context=self.context)
        self.add_cleanup_function(body.cleanup)
        body.setAutoFillBackground(False)
        body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__widget = QtWidgets.QScrollArea()
        self.__widget.setWidgetResizable(True)
        self.__widget.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.__widget.setWidget(body)

        return self.__widget

    def createWindow(self, **kwargs: Any) -> QtWidgets.QWidget:
        window = QtWidgets.QDialog(**kwargs)
        window.setAttribute(Qt.WA_DeleteOnClose, False)
        window.setWindowTitle("Metronome")

        body = MetronomeNodeWidget(
            node=self.__node,
            context=self.context)
        self.add_cleanup_function(body.cleanup)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(body)
        window.setLayout(layout)

        return window
