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
from typing import Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui.pipeline_graph import generic_node
from . import client_impl
from . import commands

logger = logging.getLogger(__name__)


class Editor(ui_base.ProjectMixin, QtWidgets.QDialog):
    def __init__(self, node: client_impl.CustomCSound, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__listeners = {}  # type: Dict[str, core.Listener]

        self.__orchestra = self.__node.orchestra
        self.__score = self.__node.score

        self.__listeners['node-messages'] = self.app.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowTitle("CSound Editor")

        icon_size = QtCore.QSize(32, 32)

        self.__apply_action = QtWidgets.QAction("Apply", self)
        self.__apply_action.setIcon(QtGui.QIcon.fromTheme('document-save'))
        self.__apply_action.setEnabled(False)
        self.__apply_action.triggered.connect(self.__apply)

        self.__apply_button = QtWidgets.QToolButton()
        self.__apply_button.setAutoRaise(True)
        self.__apply_button.setIconSize(icon_size)
        self.__apply_button.setDefaultAction(self.__apply_action)

        self.__orchestra_editor = QtWidgets.QTextEdit()
        self.__orchestra_editor.setPlainText(self.__orchestra)
        self.__orchestra_editor.textChanged.connect(self.__scriptEdited)
        self.__listeners['orchestra'] = self.__node.orchestra_changed.add(self.__orchestraChanged)

        self.__score_editor = QtWidgets.QTextEdit()
        self.__score_editor.setPlainText(self.__score)
        self.__score_editor.textChanged.connect(self.__scriptEdited)
        self.__listeners['score'] = self.__node.score_changed.add(self.__scoreChanged)

        self.__log = QtWidgets.QTextEdit()
        self.__log.setReadOnly(True)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__orchestra_editor, 2)
        l1.addWidget(self.__score_editor, 1)

        l2 = QtWidgets.QHBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addLayout(l1)
        l2.addWidget(self.__log)

        l3 = QtWidgets.QHBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__apply_button)
        l3.addStretch(1)

        l4 = QtWidgets.QVBoxLayout()
        l4.setContentsMargins(0, 0, 0, 0)
        l4.addLayout(l3)
        l4.addLayout(l2)

        self.setLayout(l4)

    def __apply(self) -> None:
        self.__orchestra = self.__orchestra_editor.toPlainText()
        self.__score = self.__score_editor.toPlainText()

        self.send_command_async(
            commands.update(
                self.__node.id,
                orchestra=self.__orchestra,
                score=self.__score),
            callback=self.__applyDone)

    def __applyDone(self, result: Any) -> None:
        self.__apply_action.setEnabled(False)

    def __scriptEdited(self) -> None:
        self.__apply_action.setEnabled(
            self.__orchestra_editor.toPlainText() != self.__node.orchestra
            or self.__score_editor.toPlainText() != self.__node.score)

    def __orchestraChanged(self, change: model.PropertyValueChange[str]) -> None:
        if change.new_value != self.__orchestra:
            logger.error("oops")

    def __scoreChanged(self, change: model.PropertyValueChange[str]) -> None:
        if change.new_value != self.__score:
            logger.error("oops")

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        log = 'http://noisicaa.odahoda.de/lv2/processor_custom_csound#csound-log'
        if log in msg:
            self.__log.moveCursor(QtGui.QTextCursor.End)
            self.__log.insertPlainText(msg[log] + '\n')


class CustomCSoundNode(generic_node.GenericNode):
    def __init__(self, *, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(node=node, **kwargs)

        assert isinstance(node, client_impl.CustomCSound), type(node).__name__
        self.__node = node  # type: client_impl.CustomCSound

        self.__editor = None  # type: Editor

    def cleanup(self) -> None:
        if self.__editor is not None:
            self.__editor.close()
            self.__editor = None

        super().cleanup()

    def buildContextMenu(self, menu: QtWidgets.QMenu) -> None:
        show_editor = menu.addAction("CSound Editor")
        show_editor.triggered.connect(self.__showEditor)

        super().buildContextMenu(menu)

    def __showEditor(self) -> None:
        if self.__editor is None:
            self.__editor = Editor(
                node=self.__node, parent=self.editor_window, context=self.context)

        self.__editor.show()
        self.__editor.raise_()
        self.__editor.activateWindow()
