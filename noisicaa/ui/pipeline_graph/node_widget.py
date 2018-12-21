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
import logging
from typing import Any, Optional, Dict, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model
from noisicaa import music
from noisicaa import node_db
from noisicaa.ui import ui_base

logger = logging.getLogger(__name__)


class ControlValuesConnector(object):
    def __init__(self, node: music.BasePipelineGraphNode) -> None:
        self.__node = node

        self.__control_values = {}  # type: Dict[str, model.ControlValue]
        for port in self.__node.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and port.type == node_db.PortDescription.KRATE_CONTROL):
                self.__control_values[port.name] = model.ControlValue(
                    value=port.float_value.default, generation=1)

        self.__control_value_listeners = []  # type: List[core.Listener]
        for control_value in self.__node.control_values:
            self.__control_values[control_value.name] = control_value.value

            self.__control_value_listeners.append(
                control_value.value_changed.add(
                    functools.partial(self.onControlValueChanged, control_value.name)))

        self.__control_values_listener = self.__node.control_values_changed.add(
            self.onControlValuesChanged)

        self.control_value_changed = core.CallbackMap[str, model.PropertyValueChange]()

    def value(self, name: str) -> float:
        return self.__control_values[name].value

    def generation(self, name: str) -> int:
        return self.__control_values[name].generation

    def cleanup(self) -> None:
        for listener in self.__control_value_listeners:
            listener.remove()
        self.__control_value_listeners.clear()

        if self.__control_values_listener is not None:
            self.__control_values_listener.remove()
            self.__control_values_listener = None

    def onControlValuesChanged(
            self, change: model.PropertyListChange[music.PipelineGraphControlValue]) -> None:
        if isinstance(change, model.PropertyListInsert):
            control_value = change.new_value

            self.control_value_changed.call(
                control_value.name,
                model.PropertyValueChange(
                    self.__node, control_value.name,
                    self.__control_values[control_value.name], control_value.value))
            self.__control_values[control_value.name] = control_value.value

            self.__control_value_listeners.insert(
                change.index,
                control_value.value_changed.add(
                    functools.partial(self.onControlValueChanged, control_value.name)))

        elif isinstance(change, model.PropertyListDelete):
            control_value = change.old_value

            for port in self.__node.description.ports:
                if port.name == control_value.name:
                    default_value = model.ControlValue(
                        value=port.float_value.default, generation=1)
                    self.control_value_changed.call(
                        control_value.name,
                        model.PropertyValueChange(
                            self.__node, control_value.name,
                            self.__control_values[control_value.name], default_value))
                    self.__control_values[control_value.name] = default_value
                    break

            listener = self.__control_value_listeners.pop(change.index)
            listener.remove()

        else:
            raise TypeError(type(change))

    def onControlValueChanged(
            self, control_value_name: str, change: model.PropertyValueChange[model.ControlValue]
    ) -> None:
        self.control_value_changed.call(
            control_value_name,
            model.PropertyValueChange(
                self.__node, control_value_name,
                self.__control_values[control_value_name], change.new_value))
        self.__control_values[control_value_name] = change.new_value


class ControlValueWidget(ui_base.ProjectMixin, QtCore.QObject):
    def __init__(
            self, *,
            node: music.BasePipelineGraphNode, port: node_db.PortDescription,
            connector: ControlValuesConnector, parent: Optional[QtWidgets.QWidget],
            **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__port = port
        self.__connector = connector
        self.__parent = parent

        self.__listeners = []  # type: List[core.Listener]
        self.__generation = self.__connector.generation(self.__port.name)

        self.__widget = QtWidgets.QLineEdit(self.__parent)
        self.__widget.setText(str(self.__connector.value(self.__port.name)))
        self.__widget.setValidator(QtGui.QDoubleValidator())
        self.__widget.editingFinished.connect(self.__onValueEdited)

        self.__listeners.append(self.__connector.control_value_changed.add(
            self.__port.name, self.__onValueChanged))

    def cleanup(self) -> None:
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

    def label(self) -> str:
        return self.__port.name

    def widget(self) -> QtWidgets.QWidget:
        return self.__widget

    def __onValueEdited(self) -> None:
        value, ok = self.__widget.locale().toDouble(self.__widget.text())
        if ok and value != self.__connector.value(self.__port.name):
            self.__generation += 1
            self.send_command_async(music.Command(
                target=self.__node.id,
                set_pipeline_graph_control_value=music.SetPipelineGraphControlValue(
                    port_name=self.__port.name,
                    float_value=value,
                    generation=self.__generation)))

    def __onValueChanged(
            self, change: model.PropertyValueChange[model.ControlValue]) -> None:
        if change.new_value.generation < self.__generation:
            return

        self.__generation = change.new_value.generation
        self.__widget.setText(str(change.new_value.value))


class NodeWidget(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        self.__listeners = []  # type: List[core.Listener]
        self.__control_values = ControlValuesConnector(self.__node)
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
        layout.setVerticalSpacing(1)
        layout.setContentsMargins(0, 0, 0, 0)
        form.setLayout(layout)

        for port in self.__node.description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and port.type == node_db.PortDescription.KRATE_CONTROL):
                widget = ControlValueWidget(
                    node=self.__node,
                    port=port,
                    connector=self.__control_values,
                    parent=form,
                    context=self.context)
                self.__control_value_widgets.append(widget)
                layout.addRow(widget.label(), widget.widget())

        scroll = QtWidgets.QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(form)
        return scroll

    # def __createUITab(self, parent: Optional[QtWidgets.QWidget]) -> QtWidgets.QWidget:
    #     node = self.__node
    #     node_description = node.description

    #     if node_description.has_ui:
    #         return PluginUI(parent=parent, node=node, context=self.context)

    #     else:
    #         tab = QtWidgets.QWidget(parent)

    #         label = QtWidgets.QLabel(tab)
    #         label.setText("This node has no native UI.")
    #         label.setAlignment(Qt.AlignHCenter)

    #         layout = QtWidgets.QVBoxLayout()
    #         layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
    #         layout.addStretch(1)
    #         layout.addWidget(label)
    #         layout.addStretch(1)
    #         tab.setLayout(layout)

    #         return tab

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
