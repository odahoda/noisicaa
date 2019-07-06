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
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import transfer_function_editor
from noisicaa.ui.graph import base_node
from . import model

logger = logging.getLogger(__name__)


class MidiVelocityMapperNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, node: model.MidiVelocityMapper, session_prefix: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__transfer_function_editor = transfer_function_editor.TransferFunctionEditor(
            transfer_function=self.__node.transfer_function,
            mutation_name_prefix=self.__node.name,
            context=self.context)
        self.add_cleanup_function(self.__transfer_function_editor.cleanup)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__transfer_function_editor)
        self.setLayout(l1)


class MidiVelocityMapperNode(base_node.Node):
    has_window = True

    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.MidiVelocityMapper), type(node).__name__
        self.__widget = None  # type: QtWidgets.QWidget
        self.__node = node  # type: model.MidiVelocityMapper

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None

        body = MidiVelocityMapperNodeWidget(
            node=self.__node,
            session_prefix='inline',
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
        window.setWindowTitle("MIDI Velocity Mapper")

        body = MidiVelocityMapperNodeWidget(
            node=self.__node,
            session_prefix='window',
            context=self.context)
        self.add_cleanup_function(body.cleanup)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(body)
        window.setLayout(layout)

        return window
