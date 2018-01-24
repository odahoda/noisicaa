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

# TODO: pylint-unclean

import functools
import logging
import math

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa import node_db
from . import ui_base
from . import dock_widget
from . import session_helpers

logger = logging.getLogger(__name__)


class Port(QtWidgets.QGraphicsRectItem):
    def __init__(
            self, parent, node_id, port_desc):
        super().__init__(parent)
        self.node_id = node_id
        self.port_desc = port_desc

        self.setAcceptHoverEvents(True)

        self.setRect(0, 0, 45, 15)
        self.setBrush(Qt.white)

        if self.port_desc.direction == node_db.PortDirection.Input:
            self.dot_pos = QtCore.QPoint(7, 7)
            sym_pos = QtCore.QPoint(45-11, -1)
        else:
            self.dot_pos = QtCore.QPoint(45-7, 7)
            sym_pos = QtCore.QPoint(3, -1)

        path = QtGui.QPainterPath()
        path.moveTo(-5, -5)
        path.lineTo(-5, 5)
        path.lineTo(5, 0)
        path.closeSubpath()
        dot = QtWidgets.QGraphicsPathItem(self)
        dot.setPath(path)
        dot.setPos(self.dot_pos)
        dot.setBrush(Qt.black)
        dot.pen().setStyle(Qt.NoPen)

        if self.port_desc.port_type == node_db.PortType.Audio:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('A')
        elif self.port_desc.port_type == node_db.PortType.KRateControl:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('C')
        elif self.port_desc.port_type == node_db.PortType.Events:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('E')
        else:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('?')
        sym.setPos(sym_pos)

    def getInfoText(self):
        text = '%s: ' % self.port_desc.name
        text += {
            (node_db.PortType.Audio, node_db.PortDirection.Input): "audio input",
            (node_db.PortType.Audio, node_db.PortDirection.Output): "audio output",
            (node_db.PortType.KRateControl, node_db.PortDirection.Input): "control input",
            (node_db.PortType.KRateControl, node_db.PortDirection.Output): "control output",
            (node_db.PortType.Events, node_db.PortDirection.Input): "event input",
            (node_db.PortType.Events, node_db.PortDirection.Output): "event output",
        }[(self.port_desc.port_type, self.port_desc.direction)]

        # if self.port_desc.port_type == node_db.PortType.Audio:
        #     if len(self.port_desc.channels) == 1:
        #         text += ', 1 channel'
        #     else:
        #         text += ', %d channels' % len(self.port_desc.channels)

        return text

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setBrush(QtGui.QColor(200, 200, 255))
        else:
            self.setBrush(Qt.white)

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        self.setHighlighted(True)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        self.setHighlighted(False)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.scene().view.startConnectionDrag(self)
            evt.accept()
            return

        return super().mousePressEvent(evt)


class QCloseIconItem(QtWidgets.QGraphicsObject):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.setAcceptHoverEvents(True)
        self.setOpacity(0.2)

        self._size = QtCore.QSizeF(16, 16)
        self._icon = QtGui.QIcon.fromTheme('edit-delete')

    def getInfoText(self):
        return "Remove this node."

    def boundingRect(self):
        return QtCore.QRectF(QtCore.QPointF(0, 0), self._size)

    def paint(self, painter, option, widget=None):
        self._icon.paint(painter, 0, 0, 16, 16)

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        self.setOpacity(1.0)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        self.setOpacity(0.4)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.clicked.emit()
            evt.accept()


class QTextEdit(QtWidgets.QTextEdit):
    editingFinished = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.setAcceptRichText(False)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

        self.__initial_text = None

    def keyPressEvent(self, evt):
        if (evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_Return):
            self.editingFinished.emit()
            self.__initial_text = self.toPlainText()
            evt.accept()
            return
        super().keyPressEvent(evt)

    def focusInEvent(self, evt):
        super().focusInEvent(evt)
        self.__initial_text = self.toPlainText()

    def focusOutEvent(self, evt):
        super().focusOutEvent(evt)
        new_text = self.toPlainText()
        if new_text != self.__initial_text:
            self.editingFinished.emit()
        self.__initial_text = None


class ControlValuesConnector(object):
    def __init__(self, node):
        self.__node = node

        self.__control_values = {}
        for port in self.__node.description.ports:
            if (port.direction == node_db.PortDirection.Input
                and port.port_type == node_db.PortType.KRateControl):
                self.__control_values[port.name] = port.default

        self.__control_value_listeners = []
        for control_value in self.__node.control_values:
            self.__control_values[control_value.name] = control_value.value

            self.__control_value_listeners.append(
                control_value.listeners.add(
                    'value', functools.partial(
                        self.onControlValueChanged, control_value.name)))

        self.__control_values_listener = self.__node.listeners.add(
            'control_values', self.onControlValuesChanged)

        self.listeners = core.CallbackRegistry()

    def __getitem__(self, name):
        return self.__control_values[name]

    def cleanup(self):
        for listener in self.__control_value_listeners:
            listener.remove()
        self.__control_value_listeners.clear()

        if self.__control_values_listener is not None:
            self.__control_values_listener.remove()
            self.__control_values_listener = None

    def onControlValuesChanged(self, action, index, control_value):
        if action == 'insert':
            self.listeners.call(
                control_value.name,
                self.__control_values[control_value.name], control_value.value)
            self.__control_values[control_value.name] = control_value.value

            self.__control_value_listeners.insert(
                index,
                control_value.listeners.add(
                    'value', functools.partial(
                        self.onControlValueChanged, control_value.name)))

        elif action == 'delete':
            for port in self.__node.description.ports:
                if port.name == control_value.name:
                    self.listeners.call(
                        control_value.name,
                        self.__control_values[control_value.name], port.default)
                    self.__control_values[control_value.name] = port.default
                    break

            listener = self.__control_value_listeners.pop(index)
            listener.remove()

        else:
            raise ValueError(action)

    def onControlValueChanged(self, control_value_name, old_value, new_value):
        self.listeners.call(
            control_value_name,
            self.__control_values[control_value_name], new_value)
        self.__control_values[control_value_name] = new_value


# TODO: This might be better it the model level.
class ParameterValuesConnector(object):
    def __init__(self, node):
        self.__node = node

        self.__parameter_values = {}
        for parameter in self.__node.description.parameters:
            if parameter.hidden:
                continue

            self.__parameter_values[parameter.name] = parameter.default

        self.__parameter_value_listeners = []
        for parameter_value in self.__node.parameter_values:
            self.__parameter_values[parameter_value.name] = parameter_value.value

            self.__parameter_value_listeners.append(
                parameter_value.listeners.add(
                    'value', functools.partial(
                        self.onParameterValueChanged, parameter_value.name)))

        self.__parameter_values_listener = self.__node.listeners.add(
            'parameter_values', self.onParameterValuesChanged)

        self.listeners = core.CallbackRegistry()

    def __getitem__(self, name):
        return self.__parameter_values[name]

    def cleanup(self):
        for listener in self.__parameter_value_listeners:
            listener.remove()
        self.__parameter_value_listeners.clear()

        if self.__parameter_values_listener is not None:
            self.__parameter_values_listener.remove()
            self.__parameter_values_listener = None

    def onParameterValuesChanged(self, action, index, parameter_value):
        if action == 'insert':
            self.listeners.call(
                parameter_value.name,
                self.__parameter_values[parameter_value.name], parameter_value.value)
            self.__parameter_values[parameter_value.name] = parameter_value.value

            self.__parameter_value_listeners.insert(
                index,
                parameter_value.listeners.add(
                    'value', functools.partial(
                        self.onParameterValueChanged, parameter_value.name)))

        elif action == 'delete':
            for parameter in self.__node.description.parameters:
                if parameter.name == parameter_value.name:
                    self.listeners.call(
                        parameter_value.name,
                        self.__parameter_values[parameter_value.name], parameter.default)
                    self.__parameter_values[parameter.name] = parameter.default
                    break

            listener = self.__parameter_value_listeners.pop(index)
            listener.remove()

        else:
            raise ValueError(action)

    def onParameterValueChanged(self, parameter_name, old_value, new_value):
        self.listeners.call(
            parameter_name,
            self.__parameter_values[parameter_name], new_value)
        self.__parameter_values[parameter_name] = new_value


class NodePropertyDialog(
        session_helpers.ManagedWindowMixin, ui_base.ProjectMixin, QtWidgets.QDialog):
    def __init__(self, node_item, **kwargs):
        super().__init__(
            session_prefix='pipeline_graph_node/%s/properties_dialog/' % node_item.node.id,
            **kwargs)

        self.setWindowTitle("%s - Properties" % node_item.node.name)

        self._node_item = node_item

        self.__listeners = []

        self._preset_edit_metadata_action = QtWidgets.QAction(
            "Edit metadata", self,
            statusTip="Edit metadata associated with the current preset.",
            triggered=self.onPresetEditMetadata)
        self._preset_load_action = QtWidgets.QAction(
            "Load", self,
            statusTip="Load state from a preset.",
            triggered=self.onPresetLoad)
        self._preset_revert_action = QtWidgets.QAction(
            "Revert", self,
            statusTip="Load state from the current preset.",
            triggered=self.onPresetRevert)
        self._preset_save_action = QtWidgets.QAction(
            "Save", self,
            statusTip="Save state to the current preset.",
            triggered=self.onPresetSave)
        self._preset_save_as_action = QtWidgets.QAction(
            "Save as", self,
            statusTip="Save state to a new preset.",
            triggered=self.onPresetSaveAs)
        self._preset_import_action = QtWidgets.QAction(
            "Import", self,
            statusTip="Import state from a file.",
            triggered=self.onPresetImport)
        self._preset_export_action = QtWidgets.QAction(
            "Export", self,
            statusTip="Export state to a file.",
            triggered=self.onPresetExport)

        menubar = QtWidgets.QMenuBar(self)
        preset_menu = menubar.addMenu("Preset")
        preset_menu.addAction(self._preset_edit_metadata_action)
        preset_menu.addSeparator()
        preset_menu.addAction(self._preset_load_action)
        preset_menu.addAction(self._preset_revert_action)
        preset_menu.addAction(self._preset_save_action)
        preset_menu.addAction(self._preset_save_as_action)
        preset_menu.addSeparator()
        preset_menu.addAction(self._preset_import_action)
        preset_menu.addAction(self._preset_export_action)

        layout = QtWidgets.QFormLayout()
        layout.setMenuBar(menubar)
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.setVerticalSpacing(1)

        node = self._node_item.node

        self._name = QtWidgets.QLineEdit(self)
        self._name.setText(node.name)
        self._name.editingFinished.connect(self.onNameEdited)
        layout.addRow("Name", self._name)

        self.__listeners.append(
            node.listeners.add('name', self.onNameChanged))

        for port in self._node_item.node_description.ports:
            if (port.direction == node_db.PortDirection.Output
                and port.port_type == node_db.PortType.Audio):
                port_property_values = dict(
                    (p.name, p.value)
                    for p in node.port_property_values
                    if p.port_name == port.name)

                # TODO: port can be bypassable without dry/wet
                if port.drywet_port is not None:
                    bypass_widget = QtWidgets.QToolButton(
                        self, checkable=True, autoRaise=True)
                    bypass_widget.setText('B')
                    bypass_widget.setChecked(
                        port_property_values.get('bypass', False))
                    drywet_widget = QtWidgets.QSlider(
                        self,
                        minimum=-100, maximum=100,
                        orientation=Qt.Horizontal, tickInterval=20,
                        tickPosition=QtWidgets.QSlider.TicksBothSides)
                    drywet_widget.setEnabled(
                        not port_property_values.get('bypass', False))
                    drywet_widget.setValue(
                        int(port_property_values.get('drywet', 0.0)))

                    bypass_widget.toggled.connect(functools.partial(
                        self.onPortBypassEdited, port, drywet_widget))
                    drywet_widget.valueChanged.connect(functools.partial(
                        self.onPortDrywetEdited, port))

                    row_layout = QtWidgets.QHBoxLayout()
                    row_layout.setSpacing(0)
                    row_layout.addWidget(bypass_widget)
                    row_layout.addWidget(drywet_widget, 1)
                    layout.addRow(
                        "Dry/wet (port <i>%s</i>)" % port.name, row_layout)

        self.__control_values = ControlValuesConnector(node)
        for port in self._node_item.node_description.ports:
            if (port.direction == node_db.PortDirection.Input
                and port.port_type == node_db.PortType.KRateControl):
                widget = QtWidgets.QLineEdit(self)
                widget.setText(str(self.__control_values[port.name]))
                widget.setValidator(QtGui.QDoubleValidator())
                widget.editingFinished.connect(functools.partial(
                    self.onFloatControlValueEdited, widget, port))
                layout.addRow(port.name, widget)

                self.__listeners.append(
                    self.__control_values.listeners.add(
                        port.name, functools.partial(
                            self.onFloatControlValueChanged, widget, port)))

        self.__parameter_values = ParameterValuesConnector(node)
        for parameter in self._node_item.node_description.parameters:
            if parameter.hidden:
                continue

            if parameter.param_type == node_db.ParameterType.Float:
                widget = QtWidgets.QLineEdit(self)
                widget.setText(parameter.to_string(self.__parameter_values[parameter.name]))
                widget.setValidator(QtGui.QDoubleValidator())
                widget.editingFinished.connect(functools.partial(
                    self.onFloatParameterEdited, widget, parameter))
                layout.addRow(parameter.display_name, widget)

                self.__listeners.append(
                    self.__parameter_values.listeners.add(
                        parameter.name, functools.partial(
                            self.onFloatParameterChanged, widget, parameter)))

            elif parameter.param_type == node_db.ParameterType.Text:
                widget = QTextEdit(self)
                widget.setPlainText(self.__parameter_values[parameter.name])
                widget.editingFinished.connect(functools.partial(
                    self.onTextParameterEdited, widget, parameter))
                layout.addRow(parameter.display_name, widget)

                self.__listeners.append(
                    self.__parameter_values.listeners.add(
                        parameter.name, functools.partial(
                            self.onTextParameterChanged, widget, parameter)))

            else:
                raise ValueError(parameter)

        self.__parameter_values_connector = ParameterValuesConnector(node)

        self.setLayout(layout)

    def cleanup(self):
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

        if self.__parameter_values is not None:
            self.__parameter_values.cleanup()
            self.__parameter_values = None

    def onPresetEditMetadata(self):
        pass

    def onPresetLoad(self):
        pass

    def onPresetRevert(self):
        pass

    def onPresetSave(self):
        self.send_command_async(
            self._node_item.node.id, 'PipelineGraphNodeToPreset',
            callback=self.onPresetSaveDone)

    def onPresetSaveDone(self, preset):
        print(preset)

    def onPresetSaveAs(self):
        pass

    def onPresetImport(self):
        path, open_filter = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Import preset",
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;noisicaä Presets (*.preset)",
            initialFilter='noisicaä Presets (*.preset)',
        )
        if not path:
            return

        self.call_async(self.onPresetImportAsync(path))

    async def onPresetImportAsync(self, path):
        logger.info("Importing preset from %s...", path)

        with open(path, 'rb') as fp:
            preset = fp.read()

        await self.project_client.send_command(
            self._node_item.node.id, 'PipelineGraphNodeFromPreset',
            preset=preset)

    def onPresetExport(self):
        path, open_filter = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption="Export preset",
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;noisicaä Presets (*.preset)",
            initialFilter='noisicaä Presets (*.preset)',
        )
        if not path:
            return

        self.call_async(self.onPresetExportAsync(path))

    async def onPresetExportAsync(self, path):
        logger.info("Exporting preset to %s...", path)

        preset = await self.project_client.send_command(
            self._node_item.node.id, 'PipelineGraphNodeToPreset')

        with open(path, 'wb') as fp:
            fp.write(preset)

    def onNameChanged(self, old_name, new_name):
        pass

    def onNameEdited(self):
        pass

    def onFloatControlValueChanged(self, widget, port, old_value, new_value):
        widget.setText(str(new_value))

    def onFloatControlValueEdited(self, widget, port):
        value, ok = widget.locale().toDouble(widget.text())
        if ok and value != self.__control_values[port.name]:
            self.send_command_async(
                self._node_item.node.id, 'SetPipelineGraphControlValue',
                port_name=port.name,
                float_value=value)

    def onFloatParameterChanged(self, widget, parameter, old_value, new_value):
        widget.setText(parameter.to_string(new_value))

    def onFloatParameterEdited(self, widget, parameter):
        value, ok = widget.locale().toDouble(widget.text())
        if ok and value != self.__parameter_values[parameter.name]:
            self.send_command_async(
                self._node_item.node.id, 'SetPipelineGraphNodeParameter',
                parameter_name=parameter.name,
                float_value=value)

    def onTextParameterChanged(self, widget, parameter, old_value, new_value):
        widget.setPlainText(new_value)

    def onTextParameterEdited(self, widget, parameter):
        value = widget.toPlainText()
        if value != self.__parameter_values[parameter.name]:
            self.send_command_async(
                self._node_item.node.id, 'SetPipelineGraphNodeParameter',
                parameter_name=parameter.name,
                str_value=value)

    def onPortBypassEdited(self, port, drywet_widget, value):
        drywet_widget.setEnabled(not value)
        self.send_command_async(
            self._node_item.node.id, 'SetPipelineGraphPortParameter',
            port_name=port.name,
            bypass=value)

    def onPortDrywetEdited(self, port, value):
        self.send_command_async(
            self._node_item.node.id, 'SetPipelineGraphPortParameter',
            port_name=port.name,
            drywet=float(value))


class NodeItem(ui_base.ProjectMixin, QtWidgets.QGraphicsRectItem):
    def __init__(self, node, view, **kwargs):
        super().__init__(**kwargs)
        self._node = node
        self._view = view

        self._listeners = []

        self._moving = False
        self._move_handle_pos = None
        self._moved = False

        self.setAcceptHoverEvents(True)

        self.setRect(0, 0, 100, 60)
        if False:  #self.desc.is_system:
            self.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 255)))
        else:
            self.setBrush(Qt.white)

        self.ports = {}
        self.connections = set()

        label = QtWidgets.QGraphicsSimpleTextItem(self)
        label.setPos(2, 2)
        label.setText(self._node.name)

        self._remove_icon = None

        if self._node.removable:
            self._remove_icon = QCloseIconItem(self)
            self._remove_icon.setPos(100 - 18, 2)
            self._remove_icon.setVisible(False)
            self._remove_icon.clicked.connect(self.onRemove)

        in_y = 25
        out_y = 25
        for port_desc in self._node.description.ports:
            if (port_desc.direction == node_db.PortDirection.Input
                and port_desc.port_type == node_db.PortType.KRateControl):
                continue

            if port_desc.direction == node_db.PortDirection.Input:
                x = -5
                y = in_y
                in_y += 20

            elif port_desc.direction == node_db.PortDirection.Output:
                x = 105-45
                y = out_y
                out_y += 20

            port = Port(
                self, self._node.id, port_desc)
            port.setPos(x, y)
            self.ports[port_desc.name] = port

        self._broken_sign = QtWidgets.QGraphicsSimpleTextItem(self)
        self._broken_sign.setText("BROKEN")
        self._broken_sign.setPen(QtGui.QColor(255, 0, 0))
        self._broken_sign.setVisible(self.is_broken)
        self._broken_listener = self.add_session_listener(
            'pipeline_graph_node/%s/broken' % self.node.id,
            self._broken_sign.setVisible)

        self.setPos(self._node.graph_pos.x, self._node.graph_pos.y)
        self._graph_pos_listener = self._node.listeners.add(
            'graph_pos', self.onGraphPosChanged)

        self._properties_dialog = NodePropertyDialog(
            node_item=self,
            parent=self.window,
            **self.context_args)

    @property
    def node(self):
        return self._node

    @property
    def node_description(self):
        return self._node.description

    @property
    def is_broken(self):
        return self.get_session_value(
            'pipeline_graph_node/%s/broken' % self.node.id, False)

    def getPort(self, port_id):
        try:
            return self.ports[port_id]
        except KeyError:
            raise KeyError(
                '%s (%s) has no port %s'
                % (self.node.name, self.node.id, port_id))

    def getInfoText(self):
        info_lines = []

        parameter_values = dict(
            (p.name, p.value) for p in self._node.parameter_values)

        for parameter in self._node.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                value = parameter_values.get(
                    parameter.name, parameter.default)
                info_lines.append("%s: %s" % (
                    parameter.display_name, value))

        return '\n'.join(info_lines)

    def cleanup(self):
        if self._broken_listener is not None:
            self._broken_listener.remove()
            self._broken_listener = None

        if self._graph_pos_listener is not None:
            self._graph_pos_listener.remove()
            self._graph_pos_listener = None

        if self._properties_dialog is not None:
            self._properties_dialog.cleanup()
            self._properties_dialog.destroy()
            self._properties_dialog = None

    def setHighlighted(self, highlighted):
        if highlighted:
            self.setBrush(QtGui.QColor(240, 240, 255))
        else:
            self.setBrush(Qt.white)

    def onGraphPosChanged(self, *args):
        self.setPos(self._node.graph_pos.x, self._node.graph_pos.y)
        for connection in self.connections:
            connection.update()

    def hoverEnterEvent(self, evt):
        super().hoverEnterEvent(evt)
        if self._remove_icon is not None:
            self._remove_icon.setVisible(True)

    def hoverLeaveEvent(self, evt):
        super().hoverLeaveEvent(evt)
        if self._remove_icon is not None:
            self._remove_icon.setVisible(False)

    def mouseDoubleClickEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self.onEdit(evt.screenPos())
            evt.accept()
        super().mouseDoubleClickEvent(evt)

    def mousePressEvent(self, evt):
        if evt.button() == Qt.LeftButton:
            self._view.nodeSelected.emit(self)

            self.grabMouse()
            self._moving = True
            self._move_handle_pos = evt.scenePos() - self.pos()
            self._moved = False
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        if self._moving:
            self.setPos(evt.scenePos() - self._move_handle_pos)
            for connection in self.connections:
                connection.update()
            self._moved = True
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if evt.button() == Qt.LeftButton and self._moving:
            if self._moved:
                self.send_command_async(
                    self._node.id, 'SetPipelineGraphNodePos',
                    graph_pos=music.Pos2F(self.pos().x(), self.pos().y()))

            self.ungrabMouse()
            self._moving = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()

        edit = menu.addAction("Edit properties...")
        edit.triggered.connect(lambda: self.onEdit(evt.screenPos()))

        if self._node.removable:
            remove = menu.addAction("Remove")
            remove.triggered.connect(self.onRemove)

        menu.exec_(evt.screenPos())
        evt.accept()

    def onRemove(self):
        self._view.send_command_async(
            self._node.parent.id, 'RemovePipelineGraphNode',
            node_id=self._node.id)

    def onEdit(self, pos=None):
        if not self._properties_dialog.isVisible():
            self._properties_dialog.show()
            if pos is not None:
                self._properties_dialog.move(pos)
        self._properties_dialog.activateWindow()


class ConnectionItem(ui_base.ProjectMixin, QtWidgets.QGraphicsPathItem):
    def __init__(self, connection=None, view=None, **kwargs):
        super().__init__(**kwargs)

        self._view = view
        self.connection = connection

        self.update()

    def update(self):
        node1_item = self._view.getNodeItem(self.connection.source_node.id)
        port1_item = node1_item.getPort(self.connection.source_port)

        node2_item = self._view.getNodeItem(self.connection.dest_node.id)
        port2_item = node2_item.getPort(self.connection.dest_port)

        pos1 = port1_item.mapToScene(port1_item.dot_pos)
        pos2 = port2_item.mapToScene(port2_item.dot_pos)
        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        # if (port1_item.port_desc.port_type != node_db.PortType.Audio
        #         or len(port1_item.port_desc.channels) == 1):
        #     path.moveTo(pos1)
        #     path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        # else:
        #     q = math.copysign(1, pos2.x()- pos1.x()) * math.copysign(1, pos2.y()- pos1.y())
        #     for d in [QtCore.QPointF(q, -1), QtCore.QPointF(-q, 1)]:
        #         path.moveTo(pos1 + d)
        #         path.cubicTo(pos1 + d + cpos, pos2 + d - cpos, pos2 + d)
        self.setPath(path)

    def setHighlighted(self, highlighted):
        if highlighted:
            effect = QtWidgets.QGraphicsDropShadowEffect()
            effect.setBlurRadius(10)
            effect.setOffset(0, 0)
            effect.setColor(Qt.blue)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)


class DragConnection(QtWidgets.QGraphicsPathItem):
    def __init__(self, port):
        super().__init__()
        self.port = port

        self.end_pos = self.port.mapToScene(self.port.dot_pos)
        self.update()

    def setEndPos(self, pos):
        self.end_pos = pos
        self.update()

    def update(self):
        pos1 = self.port.mapToScene(self.port.dot_pos)
        pos2 = self.end_pos

        if self.port.port_desc.direction == node_db.PortDirection.Input:
            pos1, pos2 = pos2, pos1

        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        # if (self.port.port_desc.port_type != node_db.PortType.Audio
        #         or len(self.port.port_desc.channels) == 1):
        #     path.moveTo(pos1)
        #     path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        # else:
        #     q = math.copysign(1, pos2.x()- pos1.x()) * math.copysign(1, pos2.y()- pos1.y())
        #     for d in [QtCore.QPointF(q, -1), QtCore.QPointF(-q, 1)]:
        #         path.moveTo(pos1 + d)
        #         path.cubicTo(pos1 + d + cpos, pos2 + d - cpos, pos2 + d)
        self.setPath(path)


class PipelineGraphScene(ui_base.ProjectMixin, QtWidgets.QGraphicsScene):
    def __init__(self, view=None, **kwargs):
        super().__init__(**kwargs)
        self.view = view

    def helpEvent(self, evt):
        item = self.itemAt(evt.scenePos(), QtGui.QTransform())
        if (item is not None
            and isinstance(item, (NodeItem, Port, QCloseIconItem))):
            info_text = item.getInfoText()
            if info_text:
                QtWidgets.QToolTip.showText(
                    evt.screenPos(), info_text, self.view)
                evt.accept()
                return
        super().helpEvent(evt)


class PipelineGraphGraphicsView(ui_base.ProjectMixin, QtWidgets.QGraphicsView):
    nodeSelected = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._scene = PipelineGraphScene(view=self, **self.context_args)
        self.setScene(self._scene)

        self._drag_connection = None
        self._drag_src_port = None
        self._drag_dest_port = None

        self._highlight_item = None

        self._nodes = []
        self._node_map = {}
        for node in self.project.pipeline_graph_nodes:
            item = NodeItem(node=node, view=self, **self.context_args)
            self._scene.addItem(item)
            self._nodes.append(item)
            self._node_map[node.id] = item

        self._pipeline_graph_nodes_listener = self.project.listeners.add(
            'pipeline_graph_nodes', self.onPipelineGraphNodesChange)

        self._connections = []
        for connection in self.project.pipeline_graph_connections:
            item = ConnectionItem(
                connection=connection, view=self, **self.context_args)
            self._scene.addItem(item)
            self._connections.append(item)
            self._node_map[connection.source_node.id].connections.add(item)
            self._node_map[connection.dest_node.id].connections.add(item)

        self._pipeline_graph_connections_listener = self.project.listeners.add(
            'pipeline_graph_connections',
            self.onPipelineGraphConnectionsChange)

        self.setAcceptDrops(True)

    def getNodeItem(self, node_id):
        return self._node_map[node_id]

    def onPipelineGraphNodesChange(self, action, *args):
        if action == 'insert':
            idx, node = args
            item = NodeItem(node=node, view=self, **self.context_args)
            self._scene.addItem(item)
            self._nodes.insert(idx, item)
            self._node_map[node.id] = item

        elif action == 'delete':
            idx, node = args
            item = self._nodes[idx]
            assert not item.connections, item.connections
            item.cleanup()
            self._scene.removeItem(item)
            del self._nodes[idx]
            del self._node_map[node.id]
            if self._highlight_item is item:
                self._highlight_item = None

        else:  # pragma: no cover
            raise AssertionError("Unknown action %r" % action)

    def onPipelineGraphConnectionsChange(self, action, *args):
        if action == 'insert':
            idx, connection = args
            item = ConnectionItem(
                connection=connection, view=self, **self.context_args)
            self._scene.addItem(item)
            self._connections.insert(idx, item)
            self._node_map[connection.source_node_id].connections.add(item)
            self._node_map[connection.dest_node_id].connections.add(item)

        elif action == 'delete':
            idx, connection = args
            item = self._connections[idx]
            self._scene.removeItem(item)
            del self._connections[idx]
            self._node_map[connection.source_node_id].connections.remove(item)
            self._node_map[connection.dest_node_id].connections.remove(item)
            if self._highlight_item is item:
                self._highlight_item = None

        else:  # pragma: no cover
            raise AssertionError("Unknown action %r" % action)

    def startConnectionDrag(self, port):
        assert self._drag_connection is None
        self._drag_connection = DragConnection(port)
        self._drag_src_port = port
        self._drag_dest_port = None
        self._scene.addItem(self._drag_connection)

    def mousePressEvent(self, evt):
        if (self._highlight_item is not None
            and isinstance(self._highlight_item, ConnectionItem)
            and evt.button() == Qt.LeftButton
            and evt.modifiers() == Qt.ShiftModifier):
            self.send_command_async(
                self.project.id, 'RemovePipelineGraphConnection',
                connection_id=self._highlight_item.connection.id)
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt):
        scene_pos = self.mapToScene(evt.pos())

        if self._drag_connection is not None:
            snap_pos = scene_pos

            src_port = self._drag_src_port
            closest_port = None
            closest_dist = None
            for node_item in self._nodes:
                for port_name, port_item in sorted(node_item.ports.items()):
                    src_desc = src_port.port_desc
                    dest_desc = port_item.port_desc

                    if dest_desc.port_type != src_desc.port_type:
                        continue
                    if dest_desc.direction == src_desc.direction:
                        continue
                    # if (dest_desc.port_type == node_db.PortType.Audio
                    #         and dest_desc.channels != src_desc.channels):
                    #     continue

                    port_pos = port_item.mapToScene(port_item.dot_pos)
                    dx = port_pos.x() - scene_pos.x()
                    dy = port_pos.y() - scene_pos.y()
                    dist = math.sqrt(dx*dx + dy*dy)
                    if dist > 30:
                        continue

                    if closest_port is None or dist < closest_dist:
                        closest_dist = dist
                        closest_port = port_item

            if closest_port is not None:
                snap_pos = closest_port.mapToScene(closest_port.dot_pos)

            self._drag_connection.setEndPos(snap_pos)

            if closest_port is not self._drag_dest_port:
                if self._drag_dest_port is not None:
                    self._drag_dest_port.setHighlighted(False)
                    self._drag_dest_port = None

                if closest_port is not None:
                    closest_port.setHighlighted(True)
                    self._drag_dest_port = closest_port

            evt.accept()
            return

        highlight_item = None
        cursor_rect = QtCore.QRectF(
            scene_pos - QtCore.QPointF(5, 5),
            scene_pos + QtCore.QPointF(5, 5))
        for item in self._scene.items(cursor_rect):
            if isinstance(item, (NodeItem, ConnectionItem)):
                highlight_item = item
                break

        if highlight_item is not self._highlight_item:
            if self._highlight_item is not None:
                self._highlight_item.setHighlighted(False)
                self._highlight_item = None

            if highlight_item is not None:
                highlight_item.setHighlighted(True)
                self._highlight_item = highlight_item

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt):
        if (evt.button() == Qt.LeftButton
            and self._drag_connection is not None):
            self._scene.removeItem(self._drag_connection)
            self._drag_connection = None

            if self._drag_dest_port is not None:
                self._drag_src_port.setHighlighted(False)
                self._drag_dest_port.setHighlighted(False)

                if self._drag_src_port.port_desc.direction != node_db.PortDirection.Output:
                    self._drag_src_port, self._drag_dest_port = self._drag_dest_port, self._drag_src_port

                assert self._drag_src_port.port_desc.direction == node_db.PortDirection.Output
                assert self._drag_dest_port.port_desc.direction == node_db.PortDirection.Input

                self.send_command_async(
                    self.project.id, 'AddPipelineGraphConnection',
                    source_node_id=self._drag_src_port.node_id,
                    source_port_name=self._drag_src_port.port_desc.name,
                    dest_node_id=self._drag_dest_port.node_id,
                    dest_port_name=self._drag_dest_port.port_desc.name)

            self._drag_src_port = None
            self._drag_dest_port = None

            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def dragEnterEvent(self, evt):
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            evt.setDropAction(Qt.CopyAction)
            evt.accept()

    def dragMoveEvent(self, evt):
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            evt.acceptProposedAction()

    def dragLeaveEvent(self, evt):
        evt.accept()

    def dropEvent(self, evt):
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            data = evt.mimeData().data(
                'application/x-noisicaa-pipeline-graph-node')
            node_uri = bytes(data).decode('utf-8')

            drop_pos = self.mapToScene(evt.pos())
            self.send_command_async(
                self.project.id, 'AddPipelineGraphNode',
                uri=node_uri,
                graph_pos=music.Pos2F(drop_pos.x(), drop_pos.y()))

            evt.acceptProposedAction()


class NodesList(ui_base.CommonMixin, QtWidgets.QListWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setDragDropMode(
            QtWidgets.QAbstractItemView.DragOnly)

        for uri, node_desc in self.app.node_db.nodes:
            list_item = QtWidgets.QListWidgetItem()
            list_item.setText(node_desc.display_name)
            list_item.setData(Qt.UserRole, uri)
            self.addItem(list_item)

    def mimeData(self, items):
        assert len(items) == 1
        item = items[0]
        data = item.data(Qt.UserRole).encode('utf-8')
        mime_data = QtCore.QMimeData()
        mime_data.setData(
            'application/x-noisicaa-pipeline-graph-node', data)
        return mime_data


class NodeListDock(dock_widget.DockWidget):
    def __init__(self, **kwargs):
        super().__init__(
            identifier='node_list',
            title="Available Nodes",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._node_list = NodesList(parent=self, **self.context_args)

        self._node_filter = QtWidgets.QLineEdit(self)
        self._node_filter.addAction(
            QtGui.QIcon.fromTheme('edit-find'),
            QtWidgets.QLineEdit.LeadingPosition)
        self._node_filter.addAction(
            QtWidgets.QAction(
                QtGui.QIcon.fromTheme('edit-clear'),
                "Clear search string", self._node_filter,
                triggered=self._node_filter.clear),
            QtWidgets.QLineEdit.TrailingPosition)
        self._node_filter.textChanged.connect(self.onNodeFilterChanged)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.setSpacing(0)
        layout.addWidget(self._node_filter)
        layout.addWidget(self._node_list, 1)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(layout)
        self.setWidget(main_area)

    def onNodeFilterChanged(self, text):
        for idx in range(self._node_list.count()):
            item = self._node_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)


class PipelineGraphView(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._graph_view = PipelineGraphGraphicsView(**self.context_args)

        self._node_list_dock = NodeListDock(parent=self.window, **self.context_args)
        self._node_list_dock.hide()

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.addWidget(self._graph_view)
        self.setLayout(layout)

    def showEvent(self, evt):
        self._node_list_dock.show()

    def hideEvent(self, evt):
        self._node_list_dock.hide()
