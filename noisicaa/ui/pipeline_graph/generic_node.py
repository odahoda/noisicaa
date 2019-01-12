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
from typing import Any, Optional, List

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa import node_db
from noisicaa.ui import ui_base
from noisicaa.ui import control_value_dial
from noisicaa.ui import control_value_connector

from . import base_node

logger = logging.getLogger(__name__)


class ControlValueWidget(control_value_connector.ControlValueConnector):
    def __init__(
            self, *,
            node: music.BasePipelineGraphNode, port: node_db.PortDescription,
            parent: Optional[QtWidgets.QWidget],
            **kwargs: Any) -> None:
        super().__init__(node=node, name=port.name, **kwargs)

        self.__node = node
        self.__port = port

        dial = control_value_dial.ControlValueDial(parent)
        dial.setRange(port.float_value.min, port.float_value.max)
        dial.setDefault(port.float_value.default)
        self.connect(dial.valueChanged, dial.setValue)

        self.__widget = QtWidgets.QWidget(parent)

        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(dial)
        layout.addStretch(1)
        self.__widget.setLayout(layout)

    def label(self) -> str:
        return self.__port.display_name + ":"

    def widget(self) -> QtWidgets.QWidget:
        return self.__widget


class GenericNodeWidget(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__node.control_value_map.init()

        self.__listeners = []  # type: List[core.Listener]
        self.__control_value_widgets = []  # type: List[ControlValueWidget]

        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__createPropertiesForm(self))
        self.setLayout(layout)

    def cleanup(self) -> None:
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

        for widget in self.__control_value_widgets:
            widget.cleanup()
        self.__control_value_widgets.clear()

    def __createPropertiesForm(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        form = QtWidgets.QWidget()
        form.setAutoFillBackground(False)
        form.setAttribute(Qt.WA_NoSystemBackground, True)

        layout = QtWidgets.QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.setVerticalSpacing(1)
        layout.setContentsMargins(0, 0, 0, 0)
        form.setLayout(layout)

        for port in self.__node.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and port.type == node_db.PortDescription.KRATE_CONTROL):
                widget = ControlValueWidget(
                    node=self.__node,
                    port=port,
                    parent=form,
                    context=self.context)
                self.__control_value_widgets.append(widget)
                layout.addRow(widget.label(), widget.widget())

        scroll = QtWidgets.QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(form)
        return scroll

    # def onPresetEditMetadata(self) -> None:
    #     pass

    # def onPresetLoad(self) -> None:
    #     pass

    # def onPresetRevert(self) -> None:
    #     pass

    # def onPresetSave(self) -> None:
    #     self.send_command_async(
    #         music.Command(
    #             target=self.__node.id,
    #             pipeline_graph_node_to_preset=music.PipelineGraphNodeToPreset()),
    #         callback=self.onPresetSaveDone)

    # def onPresetSaveDone(self, preset: bytes) -> None:
    #     print(preset)

    # def onPresetSaveAs(self) -> None:
    #     pass

    # def onPresetImport(self) -> None:
    #     path, _ = QtWidgets.QFileDialog.getOpenFileName(
    #         parent=self,
    #         caption="Import preset",
    #         #directory=self.ui_state.get(
    #         #'instruments_add_dialog_path', ''),
    #         filter="All Files (*);;noisicaä Presets (*.preset)",
    #         initialFilter='noisicaä Presets (*.preset)',
    #     )
    #     if not path:
    #         return

    #     self.call_async(self.onPresetImportAsync(path))

    # async def onPresetImportAsync(self, path: str) -> None:
    #     logger.info("Importing preset from %s...", path)

    #     with open(path, 'rb') as fp:
    #         preset = fp.read()

    #     await self.project_client.send_command(music.Command(
    #         target=self.__node.id,
    #         pipeline_graph_node_from_preset=music.PipelineGraphNodeFromPreset(
    #             preset=preset)))

    # def onPresetExport(self) -> None:
    #     path, _ = QtWidgets.QFileDialog.getSaveFileName(
    #         parent=self,
    #         caption="Export preset",
    #         #directory=self.ui_state.get(
    #         #'instruments_add_dialog_path', ''),
    #         filter="All Files (*);;noisicaä Presets (*.preset)",
    #         initialFilter='noisicaä Presets (*.preset)',
    #     )
    #     if not path:
    #         return

    #     self.call_async(self.onPresetExportAsync(path))

    # async def onPresetExportAsync(self, path: str) -> None:
    #     logger.info("Exporting preset to %s...", path)

    #     preset = await self.project_client.send_command(music.Command(
    #         target=self.__node.id,
    #         pipeline_graph_node_to_preset=music.PipelineGraphNodeToPreset()))

    #     with open(path, 'wb') as fp:
    #         fp.write(preset)


class GenericNode(base_node.Node):
    def __init__(self, *, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        return GenericNodeWidget(node=self.node(), context=self.context)
