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

import asyncio
import logging
from typing import Any, Optional

from PyQt5.QtCore import Qt
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import qprogressindicator

from . import generic_node

logger = logging.getLogger(__name__)


class PluginUI(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, *, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setParent(self.editor_window)
        self.setWindowFlags(Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowTitle(node.name)

        self.__node = node

        self.__lock = asyncio.Lock(loop=self.event_loop)
        self.__loading = False
        self.__loaded = False
        self.__show_task = None  # type: asyncio.Task
        self.__closing = False
        self.__initial_size_set = False

        self.__wid = None  # type: int

        self.__main_area = QtWidgets.QScrollArea()
        self.__main_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.__main_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.__main_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.__main_area.setWidget(self.__createLoadingWidget())
        self.__main_area.setWidgetResizable(True)

        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__main_area)
        self.setLayout(layout)

        self.__show_task = self.event_loop.create_task(self.__deferShow())
        self.__loading = True
        self.call_async(self.__loadUI())

    def cleanup(self) -> None:
        if self.__show_task is not None:
            self.__show_task.cancel()
            self.__show_task = None

        if not self.__closing:
            self.__closing = True
            self.call_async(self.__cleanupAsync())

    async def __cleanupAsync(self) -> None:
        async with self.__lock:
            if self.__wid is not None:
                await self.project_view.deletePluginUI('%016x' % self.__node.id)
                self.__wid = None

    async def __deferShow(self) -> None:
        await asyncio.sleep(0.5, loop=self.event_loop)
        self.show()
        self.raise_()
        self.activateWindow()
        self.__show_task = None

    async def __deferHide(self) -> None:
        async with self.__lock:
            # TODO: this should use self.__node.pipeline_node_id
            await self.project_view.deletePluginUI('%016x' % self.__node.id)

            self.__main_area.setWidget(self.__createLoadingWidget())
            self.__main_area.setWidgetResizable(True)

            self.__loaded = False

        self.hide()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.ignore()
        self.event_loop.create_task(self.__deferHide())

    def showEvent(self, evt: QtGui.QShowEvent) -> None:
        if not self.__loading and not self.__loaded:
            self.__loading = True
            self.call_async(self.__loadUI())

        super().showEvent(evt)

    def hideEvent(self, evt: QtGui.QHideEvent) -> None:
        if self.__show_task is not None:
            self.__show_task.cancel()
            self.__show_task = None

        super().hideEvent(evt)

    def __createLoadingWidget(self) -> QtWidgets.QWidget:
        loading_spinner = qprogressindicator.QProgressIndicator(self)
        loading_spinner.setAnimationDelay(100)
        loading_spinner.startAnimation()

        loading_text = QtWidgets.QLabel(self)
        loading_text.setText("Loading native UI...")

        hlayout = QtWidgets.QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addStretch(1)
        hlayout.addWidget(loading_spinner)
        hlayout.addWidget(loading_text)
        hlayout.addStretch(1)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addLayout(hlayout)
        layout.addStretch(1)

        loading = QtWidgets.QWidget(self)
        loading.setLayout(layout)

        return loading

    async def __loadUI(self) -> None:
        async with self.__lock:
            # TODO: this should use self.__node.pipeline_node_id
            self.__wid, size = await self.project_view.createPluginUI('%016x' % self.__node.id)

            proxy_win = QtGui.QWindow.fromWinId(self.__wid)  # type: ignore
            proxy_widget = QtWidgets.QWidget.createWindowContainer(proxy_win, self)
            proxy_widget.setMinimumSize(*size)
            #proxy_widget.setMaximumSize(*size)

            self.__main_area.setWidget(proxy_widget)
            self.__main_area.setWidgetResizable(False)

            if not self.__initial_size_set:
                view_size = self.size()
                view_size.setWidth(max(view_size.width(), size[0]))
                view_size.setHeight(max(view_size.height(), size[1]))
                logger.info("Resizing to %s", view_size)
                self.__main_area.setMinimumSize(view_size)

                self.adjustSize()

                self.__initial_size_set = True

            self.__loaded = True
            self.__loading = False

            if self.__show_task is not None:
                self.__show_task.cancel()
                self.__show_task = None
                self.show()
                self.raise_()
                self.activateWindow()


class PluginNode(generic_node.GenericNode):
    def __init__(self, *, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(node=node, **kwargs)

        self.__plugin_ui = None  # type: Optional[PluginUI]

    def cleanup(self) -> None:
        if self.__plugin_ui is not None:
            self.__plugin_ui.cleanup()

        super().cleanup()

    def buildContextMenu(self, menu: QtWidgets.QMenu) -> None:
        if self.node().description.has_ui:
            show_ui = menu.addAction("Show UI")
            show_ui.triggered.connect(self.onShowUI)

        super().buildContextMenu(menu)

    def onShowUI(self) -> None:
        if self.__plugin_ui is not None:
            self.__plugin_ui.show()
            self.__plugin_ui.raise_()
            self.__plugin_ui.activateWindow()
        else:
            self.__plugin_ui = PluginUI(node=self.node(), context=self.context)
