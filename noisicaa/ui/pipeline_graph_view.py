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
import functools
import logging
import math
from typing import Any, Optional, Union, Iterable, Dict, List, Set, Tuple  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import model
from noisicaa import music
from noisicaa import node_db
from . import ui_base
from . import dock_widget
from . import session_helpers
from . import qprogressindicator

logger = logging.getLogger(__name__)


class Port(QtWidgets.QGraphicsRectItem):
    def __init__(
            self, parent: 'NodeItem', node_id: int, port_desc: node_db.PortDescription) -> None:
        super().__init__(parent)
        self.node_id = node_id
        self.port_desc = port_desc

        self.setAcceptHoverEvents(True)

        self.setRect(0, 0, 45, 15)
        self.setBrush(Qt.white)

        if self.port_desc.direction == node_db.PortDescription.INPUT:
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

        if self.port_desc.type == node_db.PortDescription.AUDIO:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('A')
        elif self.port_desc.type == node_db.PortDescription.KRATE_CONTROL:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('C')
        elif self.port_desc.type == node_db.PortDescription.EVENTS:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('E')
        else:
            sym = QtWidgets.QGraphicsSimpleTextItem(self)
            sym.setText('?')
        sym.setPos(sym_pos)

    def getInfoText(self) -> str:
        text = '%s: ' % self.port_desc.name
        text += {
            (node_db.PortDescription.AUDIO, node_db.PortDescription.INPUT): "audio input",
            (node_db.PortDescription.AUDIO, node_db.PortDescription.OUTPUT): "audio output",
            (node_db.PortDescription.KRATE_CONTROL, node_db.PortDescription.INPUT): "control input",
            (node_db.PortDescription.KRATE_CONTROL, node_db.PortDescription.OUTPUT):
                "control output",
            (node_db.PortDescription.EVENTS, node_db.PortDescription.INPUT): "event input",
            (node_db.PortDescription.EVENTS, node_db.PortDescription.OUTPUT): "event output",
        }[(self.port_desc.type, self.port_desc.direction)]

        # if self.port_desc.type == node_db.PortDescription.AUDIO:
        #     if len(self.port_desc.channels) == 1:
        #         text += ', 1 channel'
        #     else:
        #         text += ', %d channels' % len(self.port_desc.channels)

        return text

    def setHighlighted(self, highlighted: bool) -> None:
        if highlighted:
            self.setBrush(QtGui.QColor(200, 200, 255))
        else:
            self.setBrush(Qt.white)

    def hoverEnterEvent(self, evt: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        super().hoverEnterEvent(evt)
        self.setHighlighted(True)

    def hoverLeaveEvent(self, evt: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        super().hoverLeaveEvent(evt)
        self.setHighlighted(False)

    def mousePressEvent(self, evt: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.scene().view.startConnectionDrag(self)
            evt.accept()
            return

        return super().mousePressEvent(evt)


class QCloseIconItem(QtWidgets.QGraphicsObject):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QGraphicsItem]) -> None:
        super().__init__(parent)

        self.setAcceptHoverEvents(True)
        self.setOpacity(0.2)

        self._size = QtCore.QSizeF(16, 16)
        self._icon = QtGui.QIcon.fromTheme('edit-delete')

    def getInfoText(self) -> str:
        return "Remove this node."

    def boundingRect(self) -> QtCore.QRectF:
        return QtCore.QRectF(QtCore.QPointF(0, 0), self._size)

    def paint(
            self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionGraphicsItem,
            widget: Optional[QtWidgets.QWidget] = None) -> None:
        self._icon.paint(painter, 0, 0, 16, 16)

    def hoverEnterEvent(self, evt: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        super().hoverEnterEvent(evt)
        self.setOpacity(1.0)

    def hoverLeaveEvent(self, evt: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        super().hoverLeaveEvent(evt)
        self.setOpacity(0.4)

    def mousePressEvent(self, evt: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.clicked.emit()
            evt.accept()


class QTextEdit(QtWidgets.QTextEdit):
    editingFinished = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent)

        self.setAcceptRichText(False)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

        self.__initial_text = None  # type: str

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:
        if (evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_Return):
            self.editingFinished.emit()
            self.__initial_text = self.toPlainText()
            evt.accept()
            return
        super().keyPressEvent(evt)

    def focusInEvent(self, evt: QtGui.QFocusEvent) -> None:
        super().focusInEvent(evt)
        self.__initial_text = self.toPlainText()

    def focusOutEvent(self, evt: QtGui.QFocusEvent) -> None:
        super().focusOutEvent(evt)
        new_text = self.toPlainText()
        if new_text != self.__initial_text:
            self.editingFinished.emit()
        self.__initial_text = None


class PluginUI(ui_base.ProjectMixin, QtWidgets.QScrollArea):
    def __init__(self, *, node: music.BasePipelineGraphNode, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.__node = node

        self.__lock = asyncio.Lock(loop=self.event_loop)
        self.__loading = False
        self.__loaded = False
        self.__hiding_task = None  # type: asyncio.Task
        self.__closing = False
        self.__initial_size_set = False

        self.__wid = None  # type: int

        self.setWidget(self.__createLoadingWidget())
        self.setWidgetResizable(True)

    def cleanup(self) -> None:
        if self.__hiding_task is not None:
            self.__hiding_task.cancel()
            self.__hiding_task = None

        if not self.__closing:
            self.__closing = True
            self.call_async(self.__cleanupAsync())

    async def __cleanupAsync(self) -> None:
        async with self.__lock:
            if self.__wid is not None:
                await self.project_view.deletePluginUI('%016x' % self.__node.id)
                self.__wid = None

    def showEvent(self, evt: QtGui.QShowEvent) -> None:
        if self.__hiding_task is not None:
            self.__hiding_task.cancel()
            self.__hiding_task = None

        if not self.__loading and not self.__loaded:
            self.__loading = True
            self.call_async(self.__loadUI())

        super().showEvent(evt)

    def hideEvent(self, evt: QtGui.QHideEvent) -> None:
        if self.__hiding_task is None and self.__loaded:
            self.__hiding_task = self.event_loop.create_task(self.__unloadUI())

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

            self.setWidget(proxy_widget)
            self.setWidgetResizable(False)

            if not self.__initial_size_set:
                view_size = self.size()
                view_size.setWidth(max(view_size.width(), size[0]))
                view_size.setHeight(max(view_size.height(), size[1]))
                logger.info("Resizing to %s", view_size)
                self.setMinimumSize(view_size)

                parent = self.parentWidget()
                while True:
                    if isinstance(parent, QtWidgets.QDialog):
                        parent.adjustSize()
                        break
                    parent = parent.parentWidget()

                self.__initial_size_set = True

            self.__loaded = True
            self.__loading = False

    async def __unloadUI(self) -> None:
        #await asyncio.sleep(10, loop=self.event_loop)

        async with self.__lock:
            # TODO: this should use self.__node.pipeline_node_id
            await self.project_view.deletePluginUI('%016x' % self.__node.id)

            self.setWidget(self.__createLoadingWidget())
            self.setWidgetResizable(True)

            self.__loaded = False
            self.__hiding_task = None


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
            node_item: 'NodeItem', port: node_db.PortDescription,
            connector: ControlValuesConnector, parent: Optional[QtWidgets.QWidget],
            **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_item = node_item
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
                target=self.__node_item.node.id,
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


class NodePropertyDialog(
        session_helpers.ManagedWindowMixin, ui_base.ProjectMixin, QtWidgets.QDialog):
    def __init__(self, node_item: 'NodeItem', **kwargs: Any) -> None:
        super().__init__(
            session_prefix='pipeline_graph_node/%s/properties_dialog/' % node_item.node.id,
            **kwargs)

        self.setWindowTitle("%s - Properties" % node_item.node.name)

        self._node_item = node_item

        self.__listeners = []  # type: List[core.Listener]

        self._preset_edit_metadata_action = QtWidgets.QAction("Edit metadata", self)
        self._preset_edit_metadata_action.setStatusTip(
            "Edit metadata associated with the current preset.")
        self._preset_edit_metadata_action.triggered.connect(self.onPresetEditMetadata)

        self._preset_load_action = QtWidgets.QAction("Load", self)
        self._preset_load_action.setStatusTip("Load state from a preset.")
        self._preset_load_action.triggered.connect(self.onPresetLoad)

        self._preset_revert_action = QtWidgets.QAction("Revert", self)
        self._preset_revert_action.setStatusTip("Load state from the current preset.")
        self._preset_revert_action.triggered.connect(self.onPresetRevert)

        self._preset_save_action = QtWidgets.QAction("Save", self)
        self._preset_save_action.setStatusTip("Save state to the current preset.")
        self._preset_save_action.triggered.connect(self.onPresetSave)

        self._preset_save_as_action = QtWidgets.QAction("Save as", self)
        self._preset_save_as_action.setStatusTip("Save state to a new preset.")
        self._preset_save_as_action.triggered.connect(self.onPresetSaveAs)

        self._preset_import_action = QtWidgets.QAction("Import", self)
        self._preset_import_action.setStatusTip("Import state from a file.")
        self._preset_import_action.triggered.connect(self.onPresetImport)

        self._preset_export_action = QtWidgets.QAction("Export", self)
        self._preset_export_action.setStatusTip("Export state to a file.")
        self._preset_export_action.triggered.connect(self.onPresetExport)

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

        props = QtWidgets.QWidget()
        prop_layout = QtWidgets.QFormLayout()
        prop_layout.setVerticalSpacing(1)
        props.setLayout(prop_layout)

        node = self._node_item.node

        self._name = QtWidgets.QLineEdit(props)
        self._name.setText(node.name)
        self._name.editingFinished.connect(self.onNameEdited)
        prop_layout.addRow("Name", self._name)

        self.__listeners.append(node.name_changed.add(self.onNameChanged))

        self.__control_values = ControlValuesConnector(node)
        self.__control_value_widgets = []  # type: List[ControlValueWidget]
        for port in self._node_item.node_description.ports:
            if (port.direction == node_db.PortDescription.INPUT
                    and port.type == node_db.PortDescription.KRATE_CONTROL):
                widget = ControlValueWidget(
                    node_item=self._node_item,
                    port=port,
                    connector=self.__control_values,
                    parent=props,
                    context=self.context)
                self.__control_value_widgets.append(widget)
                prop_layout.addRow(widget.label(), widget.widget())

        prop_tab = QtWidgets.QScrollArea()
        prop_tab.setWidgetResizable(True)
        prop_tab.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        prop_tab.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        prop_tab.setWidget(props)

        tabs = QtWidgets.QTabWidget(self)
        tabs.setTabPosition(QtWidgets.QTabWidget.West)
        tabs.addTab(prop_tab, "Properties")
        ui_index = tabs.addTab(self.__createUITab(tabs), "UI")

        if node.description.has_ui:
            tabs.setCurrentIndex(ui_index)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setMenuBar(menubar)
        main_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        main_layout.setSpacing(1)
        main_layout.addWidget(tabs)
        self.setLayout(main_layout)

    def cleanup(self) -> None:
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

        for widget in self.__control_value_widgets:
            widget.cleanup()
        self.__control_value_widgets.clear()

    def __createUITab(self, parent: Optional[QtWidgets.QWidget]) -> QtWidgets.QWidget:
        node = self._node_item.node
        node_description = node.description

        if node_description.has_ui:
            return PluginUI(parent=parent, node=node, context=self.context)

        else:
            tab = QtWidgets.QWidget(parent)

            label = QtWidgets.QLabel(tab)
            label.setText("This node has no native UI.")
            label.setAlignment(Qt.AlignHCenter)

            layout = QtWidgets.QVBoxLayout()
            layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
            layout.addStretch(1)
            layout.addWidget(label)
            layout.addStretch(1)
            tab.setLayout(layout)

            return tab

    def onPresetEditMetadata(self) -> None:
        pass

    def onPresetLoad(self) -> None:
        pass

    def onPresetRevert(self) -> None:
        pass

    def onPresetSave(self) -> None:
        self.send_command_async(
            music.Command(
                target=self._node_item.node.id,
                pipeline_graph_node_to_preset=music.PipelineGraphNodeToPreset()),
            callback=self.onPresetSaveDone)

    def onPresetSaveDone(self, preset: bytes) -> None:
        print(preset)

    def onPresetSaveAs(self) -> None:
        pass

    def onPresetImport(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
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

    async def onPresetImportAsync(self, path: str) -> None:
        logger.info("Importing preset from %s...", path)

        with open(path, 'rb') as fp:
            preset = fp.read()

        await self.project_client.send_command(music.Command(
            target=self._node_item.node.id,
            pipeline_graph_node_from_preset=music.PipelineGraphNodeFromPreset(
                preset=preset)))

    def onPresetExport(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
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

    async def onPresetExportAsync(self, path: str) -> None:
        logger.info("Exporting preset to %s...", path)

        preset = await self.project_client.send_command(music.Command(
            target=self._node_item.node.id,
            pipeline_graph_node_to_preset=music.PipelineGraphNodeToPreset()))

        with open(path, 'wb') as fp:
            fp.write(preset)

    def onNameChanged(self, change: model.PropertyValueChange[str]) -> None:
        pass

    def onNameEdited(self) -> None:
        pass


class NodeItem(ui_base.ProjectMixin, QtWidgets.QGraphicsRectItem):
    def __init__(
            self, node: music.BasePipelineGraphNode, view: 'PipelineGraphGraphicsView',
            **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._node = node
        self._view = view

        self._listeners = []  # type: List[core.Listener]

        self._moving = False
        self._move_handle_pos = None  # type: QtCore.QPointF
        self._moved = False

        self.setAcceptHoverEvents(True)

        self.setRect(0, 0, 100, 60)
        if False:  #self.desc.is_system:  # pylint: disable=using-constant-test
            self.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 255)))
        else:
            self.setBrush(Qt.white)

        self.ports = {}  # type: Dict[str, Port]
        self.connections = set()  # type: Set[ConnectionItem]

        label = QtWidgets.QGraphicsSimpleTextItem(self)
        label.setPos(2, 2)
        label.setText(self._node.name)

        self._remove_icon = None  # type: Optional[QCloseIconItem]

        if self._node.removable:
            self._remove_icon = QCloseIconItem(self)
            self._remove_icon.setPos(100 - 18, 2)
            self._remove_icon.setVisible(False)
            self._remove_icon.clicked.connect(self.onRemove)

        in_y = 25
        out_y = 25
        for port_desc in self._node.description.ports:
            if (port_desc.direction == node_db.PortDescription.INPUT
                    and port_desc.type == node_db.PortDescription.KRATE_CONTROL):
                continue

            if port_desc.direction == node_db.PortDescription.INPUT:
                x = -5
                y = in_y
                in_y += 20

            elif port_desc.direction == node_db.PortDescription.OUTPUT:
                x = 105-45
                y = out_y
                out_y += 20

            port = Port(self, self._node.id, port_desc)
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
        self._graph_pos_listener = self._node.graph_pos_changed.add(self.onGraphPosChanged)

        self._properties_dialog = NodePropertyDialog(
            node_item=self,
            parent=self.editor_window,
            context=self.context)

    @property
    def node(self) -> music.BasePipelineGraphNode:
        return self._node

    @property
    def node_description(self) -> node_db.NodeDescription:
        return self._node.description

    @property
    def is_broken(self) -> bool:
        return self.get_session_value('pipeline_graph_node/%s/broken' % self.node.id, False)

    def getPort(self, port_id: str) -> Port:
        try:
            return self.ports[port_id]
        except KeyError:
            raise KeyError(
                '%s (%s) has no port %s'
                % (self.node.name, self.node.id, port_id))

    def getInfoText(self) -> str:
        return ""

    def cleanup(self) -> None:
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

    def setHighlighted(self, highlighted: bool) -> None:
        if highlighted:
            self.setBrush(QtGui.QColor(240, 240, 255))
        else:
            self.setBrush(Qt.white)

    def onGraphPosChanged(self, *args: Any) -> None:
        self.setPos(self._node.graph_pos.x, self._node.graph_pos.y)
        for connection in self.connections:
            connection.updatePath()

    def hoverEnterEvent(self, evt: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        super().hoverEnterEvent(evt)
        if self._remove_icon is not None:
            self._remove_icon.setVisible(True)

    def hoverLeaveEvent(self, evt: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        super().hoverLeaveEvent(evt)
        if self._remove_icon is not None:
            self._remove_icon.setVisible(False)

    def mouseDoubleClickEvent(self, evt: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self.onEdit(evt.screenPos())
            evt.accept()
        super().mouseDoubleClickEvent(evt)

    def mousePressEvent(self, evt: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if evt.button() == Qt.LeftButton:
            self._view.nodeSelected.emit(self)

            self.grabMouse()
            self._moving = True
            self._move_handle_pos = evt.scenePos() - self.pos()
            self._moved = False
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self._moving:
            self.setPos(evt.scenePos() - self._move_handle_pos)
            for connection in self.connections:
                connection.updatePath()
            self._moved = True
            evt.accept()
            return

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self._moving:
            if self._moved:
                self.send_command_async(music.Command(
                    target=self._node.id,
                    set_pipeline_graph_node_pos=music.SetPipelineGraphNodePos(
                        graph_pos=model.Pos2F(self.pos().x(), self.pos().y()).to_proto())))

            self.ungrabMouse()
            self._moving = False
            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def contextMenuEvent(self, evt: QtWidgets.QGraphicsSceneContextMenuEvent) -> None:
        menu = QtWidgets.QMenu()

        edit = menu.addAction("Edit properties...")
        edit.triggered.connect(lambda: self.onEdit(evt.screenPos()))

        if self._node.removable:
            remove = menu.addAction("Remove")
            remove.triggered.connect(self.onRemove)

        menu.exec_(evt.screenPos())
        evt.accept()

    def onRemove(self) -> None:
        self._view.send_command_async(music.Command(
            target=self._node.parent.id,
            remove_pipeline_graph_node=music.RemovePipelineGraphNode(
                node_id=self._node.id)))

    def onEdit(self, pos: Optional[QtCore.QPoint] = None) -> None:
        if not self._properties_dialog.isVisible():
            self._properties_dialog.show()
            if pos is not None:
                self._properties_dialog.move(pos)
        self._properties_dialog.activateWindow()


class ConnectionItem(ui_base.ProjectMixin, QtWidgets.QGraphicsPathItem):
    def __init__(
            self, *,
            connection: music.PipelineGraphConnection, view: 'PipelineGraphGraphicsView',
            **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._view = view
        self.connection = connection

        self.updatePath()

    def updatePath(self) -> None:
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
        # if (port1_item.port_desc.type != node_db.PortDescription.AUDIO
        #         or len(port1_item.port_desc.channels) == 1):
        #     path.moveTo(pos1)
        #     path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        # else:
        #     q = math.copysign(1, pos2.x()- pos1.x()) * math.copysign(1, pos2.y()- pos1.y())
        #     for d in [QtCore.QPointF(q, -1), QtCore.QPointF(-q, 1)]:
        #         path.moveTo(pos1 + d)
        #         path.cubicTo(pos1 + d + cpos, pos2 + d - cpos, pos2 + d)
        self.setPath(path)

    def setHighlighted(self, highlighted: bool) -> None:
        if highlighted:
            effect = QtWidgets.QGraphicsDropShadowEffect()
            effect.setBlurRadius(10)
            effect.setOffset(0, 0)
            effect.setColor(Qt.blue)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)


class DragConnection(QtWidgets.QGraphicsPathItem):
    def __init__(self, port: Port) -> None:
        super().__init__()
        self.port = port

        self.end_pos = self.port.mapToScene(self.port.dot_pos)
        self.updatePath()

    def setEndPos(self, pos: QtCore.QPointF) -> None:
        self.end_pos = pos
        self.updatePath()

    def updatePath(self) -> None:
        pos1 = self.port.mapToScene(self.port.dot_pos)
        pos2 = self.end_pos

        if self.port.port_desc.direction == node_db.PortDescription.INPUT:
            pos1, pos2 = pos2, pos1

        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        # if (self.port.port_desc.type != node_db.PortDescription.AUDIO
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
    def __init__(self, *, view: 'PipelineGraphGraphicsView', **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.view = view

    def helpEvent(self, evt: QtWidgets.QGraphicsSceneHelpEvent) -> None:
        item = self.itemAt(evt.scenePos(), QtGui.QTransform())
        if item is not None and isinstance(item, (NodeItem, Port, QCloseIconItem)):
            info_text = item.getInfoText()
            if info_text:
                QtWidgets.QToolTip.showText(
                    evt.screenPos(), info_text, self.view)
                evt.accept()
                return
        super().helpEvent(evt)


class PipelineGraphGraphicsView(ui_base.ProjectMixin, QtWidgets.QGraphicsView):
    nodeSelected = QtCore.pyqtSignal(object)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._scene = PipelineGraphScene(view=self, context=self.context)
        self.setScene(self._scene)

        self._drag_connection = None  # type: DragConnection
        self._drag_src_port = None  # type: Port
        self._drag_dest_port = None  # type: Port

        self._highlight_item = None  # type: Optional[Union[NodeItem, ConnectionItem]]

        self._nodes = []  # type: List[NodeItem]
        self._node_map = {}  # type: Dict[int, NodeItem]
        for node in self.project.pipeline_graph_nodes:
            nitem = NodeItem(node=node, view=self, context=self.context)
            self._scene.addItem(nitem)
            self._nodes.append(nitem)
            self._node_map[node.id] = nitem

        self._pipeline_graph_nodes_listener = self.project.pipeline_graph_nodes_changed.add(
            self.onPipelineGraphNodesChange)

        self._connections = []  # type: List[ConnectionItem]
        for connection in self.project.pipeline_graph_connections:
            citem = ConnectionItem(connection=connection, view=self, context=self.context)
            self._scene.addItem(citem)
            self._connections.append(citem)
            self._node_map[connection.source_node.id].connections.add(citem)
            self._node_map[connection.dest_node.id].connections.add(citem)

        self._pipeline_graph_connections_listener = \
            self.project.pipeline_graph_connections_changed.add(
                self.onPipelineGraphConnectionsChange)

        self.setAcceptDrops(True)

    def getNodeItem(self, node_id: int) -> NodeItem:
        return self._node_map[node_id]

    def onPipelineGraphNodesChange(
            self, change: model.PropertyListChange[music.BasePipelineGraphNode]) -> None:
        if isinstance(change, model.PropertyListInsert):
            item = NodeItem(node=change.new_value, view=self, context=self.context)
            self._scene.addItem(item)
            self._nodes.insert(change.index, item)
            self._node_map[change.new_value.id] = item

        elif isinstance(change, model.PropertyListDelete):
            item = self._nodes[change.index]
            assert not item.connections, item.connections
            item.cleanup()
            self._scene.removeItem(item)
            del self._nodes[change.index]
            del self._node_map[change.old_value.id]
            if self._highlight_item is item:
                self._highlight_item = None

        else:  # pragma: no cover
            raise TypeError(type(change))

    def onPipelineGraphConnectionsChange(
            self, change: model.PropertyListChange[music.PipelineGraphConnection]) -> None:
        if isinstance(change, model.PropertyListInsert):
            item = ConnectionItem(
                connection=change.new_value, view=self, context=self.context)
            self._scene.addItem(item)
            self._connections.insert(change.index, item)
            self._node_map[change.new_value.source_node.id].connections.add(item)
            self._node_map[change.new_value.dest_node.id].connections.add(item)

        elif isinstance(change, model.PropertyListDelete):
            item = self._connections[change.index]
            self._scene.removeItem(item)
            del self._connections[change.index]
            self._node_map[change.old_value.source_node.id].connections.remove(item)
            self._node_map[change.old_value.dest_node.id].connections.remove(item)
            if self._highlight_item is item:
                self._highlight_item = None

        else:  # pragma: no cover
            raise TypeError(type(change))

    def startConnectionDrag(self, port: Port) -> None:
        assert self._drag_connection is None
        self._drag_connection = DragConnection(port)
        self._drag_src_port = port
        self._drag_dest_port = None
        self._scene.addItem(self._drag_connection)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if (self._highlight_item is not None
                and isinstance(self._highlight_item, ConnectionItem)
                and evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.ShiftModifier):
            self.send_command_async(music.Command(
                target=self.project.id,
                remove_pipeline_graph_connection=music.RemovePipelineGraphConnection(
                    connection_id=self._highlight_item.connection.id)))
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        scene_pos = self.mapToScene(evt.pos())

        if self._drag_connection is not None:
            snap_pos = scene_pos

            src_port = self._drag_src_port
            closest_port = None  # type: Port
            closest_dist = None  # type: float
            for node_item in self._nodes:
                for _, port_item in sorted(node_item.ports.items()):
                    src_desc = src_port.port_desc
                    dest_desc = port_item.port_desc

                    if dest_desc.type != src_desc.type:
                        continue
                    if dest_desc.direction == src_desc.direction:
                        continue
                    # if (dest_desc.type == node_db.PortDescription.AUDIO
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

        highlight_item = None  # type: Union[NodeItem, ConnectionItem]
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

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self._drag_connection is not None:
            self._scene.removeItem(self._drag_connection)
            self._drag_connection = None

            if self._drag_dest_port is not None:
                self._drag_src_port.setHighlighted(False)
                self._drag_dest_port.setHighlighted(False)

                if self._drag_src_port.port_desc.direction != node_db.PortDescription.OUTPUT:
                    self._drag_src_port, self._drag_dest_port = (
                        self._drag_dest_port, self._drag_src_port)

                assert self._drag_src_port.port_desc.direction == node_db.PortDescription.OUTPUT
                assert self._drag_dest_port.port_desc.direction == node_db.PortDescription.INPUT

                self.send_command_async(music.Command(
                    target=self.project.id,
                    add_pipeline_graph_connection=music.AddPipelineGraphConnection(
                        source_node_id=self._drag_src_port.node_id,
                        source_port_name=self._drag_src_port.port_desc.name,
                        dest_node_id=self._drag_dest_port.node_id,
                        dest_port_name=self._drag_dest_port.port_desc.name)))

            self._drag_src_port = None
            self._drag_dest_port = None

            evt.accept()
            return

        super().mouseReleaseEvent(evt)

    def dragEnterEvent(self, evt: QtGui.QDragEnterEvent) -> None:
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            evt.setDropAction(Qt.CopyAction)
            evt.accept()

    def dragMoveEvent(self, evt: QtGui.QDragMoveEvent) -> None:
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            evt.acceptProposedAction()

    def dragLeaveEvent(self, evt: QtGui.QDragLeaveEvent) -> None:
        evt.accept()

    def dropEvent(self, evt: QtGui.QDropEvent) -> None:
        if 'application/x-noisicaa-pipeline-graph-node' in evt.mimeData().formats():
            data = evt.mimeData().data('application/x-noisicaa-pipeline-graph-node').data()
            node_uri = data.decode('utf-8')

            drop_pos = self.mapToScene(evt.pos())
            self.send_command_async(music.Command(
                target=self.project.id,
                add_pipeline_graph_node=music.AddPipelineGraphNode(
                    uri=node_uri,
                    graph_pos=model.Pos2F(drop_pos.x(), drop_pos.y()).to_proto())))

            evt.acceptProposedAction()


class NodesList(ui_base.CommonMixin, QtWidgets.QListWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

        for uri, node_desc in self.app.node_db.nodes:
            list_item = QtWidgets.QListWidgetItem()
            list_item.setText(node_desc.display_name)
            list_item.setData(Qt.UserRole, uri)
            self.addItem(list_item)

    def mimeData(self, items: Iterable[QtWidgets.QListWidgetItem]) -> QtCore.QMimeData:
        items = list(items)
        assert len(items) == 1
        item = items[0]
        data = item.data(Qt.UserRole).encode('utf-8')
        mime_data = QtCore.QMimeData()
        mime_data.setData('application/x-noisicaa-pipeline-graph-node', data)
        return mime_data


class NodeListDock(dock_widget.DockWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            identifier='node_list',
            title="Available Nodes",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self._node_list = NodesList(parent=self, context=self.context)

        self._node_filter = QtWidgets.QLineEdit(self)
        self._node_filter.addAction(
            QtGui.QIcon.fromTheme('edit-find'),
            QtWidgets.QLineEdit.LeadingPosition)
        self._node_filter.textChanged.connect(self.onNodeFilterChanged)

        clear_action = QtWidgets.QAction("Clear search string", self._node_filter)
        clear_action.setIcon(QtGui.QIcon.fromTheme('edit-clear'))
        clear_action.triggered.connect(self._node_filter.clear)
        self._node_filter.addAction(clear_action, QtWidgets.QLineEdit.TrailingPosition)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.setSpacing(0)
        layout.addWidget(self._node_filter)
        layout.addWidget(self._node_list, 1)

        main_area = QtWidgets.QWidget()
        main_area.setLayout(layout)
        self.setWidget(main_area)

    def onNodeFilterChanged(self, text: str) -> None:
        for idx in range(self._node_list.count()):
            item = self._node_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)


class PipelineGraphView(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._graph_view = PipelineGraphGraphicsView(context=self.context)

        self._node_list_dock = NodeListDock(parent=self.editor_window, context=self.context)
        self._node_list_dock.hide()

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        layout.addWidget(self._graph_view)
        self.setLayout(layout)

    def showEvent(self, evt: QtGui.QShowEvent) -> None:
        self._node_list_dock.show()

    def hideEvent(self, evt: QtGui.QHideEvent) -> None:
        self._node_list_dock.hide()
