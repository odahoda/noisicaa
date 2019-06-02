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

import asyncio
import logging
import random
import uuid
from typing import cast, Any, Optional, List

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import instrument_db
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa.builtin_nodes.instrument import processor_messages as instrument
from noisicaa.builtin_nodes.midi_source import processor_messages as midi_source
from . import piano
from . import qprogressindicator
from . import ui_base
from . import instrument_list

logger = logging.getLogger(__name__)

# instrument info
# collection info
# rescan
# - highlight broken
# instruments
# - group by collection
# - filter: only broken, collection, type
# - type icons
# - sorting
# - add/remove


class FilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, source: instrument_list.InstrumentList, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.setSourceModel(source)

        self.__source = source
        self.__filter = []  # type: List[str]

    def setFilter(self, text: str) -> None:
        words = text.split()
        words = [word.strip() for word in words]
        words = [word for word in words if word]
        words = [word.lower() for word in words]
        self.__filter = words
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QtCore.QModelIndex) -> bool:
        if not self.__filter:
            return True

        if not parent.isValid():
            return True

        parent_item = cast(instrument_list.AbstractFolder, self.__source.item(parent))
        item = parent_item.children[row]

        if isinstance(item, instrument_list.AbstractFolder):
            # Urgh... this is O(n^2)
            folder_index = self.__source.index(row, 0, parent)
            return any(
                self.filterAcceptsRow(subrow, folder_index)
                for subrow in range(len(item.children)))

        return all(word in item.display_name.lower() for word in self.__filter)


class LibraryView(QtWidgets.QTreeView):
    currentIndexChanged = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setHeaderHidden(True)
        self.setMinimumWidth(250)

    def currentChanged(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        self.currentIndexChanged.emit(current)

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu()

        expand_all = menu.addAction("Expand all")
        expand_all.triggered.connect(self.expandAll)

        collaps_all = menu.addAction("Collaps all")
        collaps_all.triggered.connect(self.collapseAll)

        menu.exec_(evt.globalPos())
        evt.accept()


class InstrumentLibraryDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    instrumentChanged = QtCore.pyqtSignal(instrument_db.InstrumentDescription)

    def __init__(
            self, parent: Optional[QtWidgets.QWidget] = None, selectButton: bool = False,
            **kwargs: Any) -> None:
        super().__init__(parent=parent, **kwargs)

        logger.info("InstrumentLibrary created")

        self.__instrument_lock = asyncio.Lock(loop=self.event_loop)

        self.__track_id = random.getrandbits(64)
        self.__instrument_id = None  # type: str
        self.__midi_source_id = None  # type: str

        self.__instrument = None  # type: instrument_db.InstrumentDescription
        self.__instrument_loader_task = None  # type: asyncio.Task
        self.__instrument_queue = asyncio.Queue(loop=self.event_loop)  # type: asyncio.Queue

        self.setWindowTitle("noisicaä - Instrument Library")

        menubar = QtWidgets.QMenuBar(self)
        library_menu = menubar.addMenu("Library")

        rescan_action = QtWidgets.QAction("Rescan", self)
        rescan_action.setStatusTip("Rescan library for updates.")
        rescan_action.triggered.connect(self.onRescan)
        library_menu.addAction(rescan_action)

        splitter = QtWidgets.QSplitter(self)
        splitter.setChildrenCollapsible(False)

        left = QtWidgets.QWidget(self)
        splitter.addWidget(left)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        left.setLayout(layout)

        self.instruments_search = QtWidgets.QLineEdit(self)
        layout.addWidget(self.instruments_search)
        search_action = QtWidgets.QAction()
        search_action.setIcon(QtGui.QIcon.fromTheme('edit-find'))
        self.instruments_search.addAction(search_action, QtWidgets.QLineEdit.LeadingPosition)
        clear_action = QtWidgets.QAction("Clear search string", self.instruments_search)
        clear_action.setIcon(QtGui.QIcon.fromTheme('edit-clear'))
        clear_action.triggered.connect(self.instruments_search.clear)
        self.instruments_search.addAction(clear_action, QtWidgets.QLineEdit.TrailingPosition)
        self.instruments_search.textChanged.connect(self.onInstrumentSearchChanged)

        self.__model_filter = FilterModel(self.app.instrument_list)
        self.__view = LibraryView(self)
        self.__view.setModel(self.__model_filter)
        layout.addWidget(self.__view, 1)
        self.__view.currentIndexChanged.connect(self.onInstrumentItemSelected)

        instrument_info = QtWidgets.QWidget(self)
        splitter.addWidget(instrument_info)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        instrument_info.setLayout(layout)

        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.instrument_name = QtWidgets.QLineEdit(self)
        self.instrument_name.setReadOnly(True)
        form_layout.addRow("Name", self.instrument_name)

        self.instrument_data = QtWidgets.QTextEdit(self)
        self.instrument_data.setReadOnly(True)
        form_layout.addRow("Description", self.instrument_data)

        layout.addStretch(1)

        self.piano = piano.PianoWidget(self)
        self.piano.setEnabled(False)
        self.piano.noteOn.connect(self.onNoteOn)
        self.piano.noteOff.connect(self.onNoteOff)
        layout.addWidget(self.piano)

        self.spinner = QtWidgets.QWidget(self)
        self.spinner.setVisible(False)

        spinner_indicator = qprogressindicator.QProgressIndicator(self.spinner)
        spinner_indicator.setAnimationDelay(100)
        spinner_indicator.startAnimation()

        spinner_label = QtWidgets.QLabel(self.spinner)
        spinner_label.setAlignment(Qt.AlignVCenter)
        spinner_label.setText("Loading instrument...")

        spinner_layout = QtWidgets.QHBoxLayout()
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        spinner_layout.addStretch(1)
        spinner_layout.addWidget(spinner_indicator)
        spinner_layout.addWidget(spinner_label)
        spinner_layout.addStretch(1)
        self.spinner.setLayout(spinner_layout)

        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)

        if selectButton:
            select = QtWidgets.QPushButton("Select")
            select.clicked.connect(self.accept)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.spinner)
        buttons.addStretch(1)
        if selectButton:
            buttons.addWidget(select)
        buttons.addWidget(close)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMenuBar(menubar)
        layout.addWidget(splitter, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def instrument(self) -> instrument_db.InstrumentDescription:
        return self.__instrument

    async def setup(self) -> None:
        logger.info("Setting up instrument library dialog...")

        self.__instrument_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            'root',
            description=self.app.node_db.get_node_description('builtin://instrument'),
            id=self.__instrument_id)
        await self.audioproc_client.connect_ports(
            'root',
            self.__instrument_id, 'out:left', 'sink', 'in:left')
        await self.audioproc_client.connect_ports(
            'root',
            self.__instrument_id, 'out:right', 'sink', 'in:right')

        self.__midi_source_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            'root',
            description=self.app.node_db.get_node_description('builtin://midi-source'),
            id=self.__midi_source_id)
        await self.sendNodeMessage(midi_source.update(
            self.__midi_source_id, device_uri='null://'))

        await self.audioproc_client.connect_ports(
            'root',
            self.__midi_source_id, 'out', self.__instrument_id, 'in')

        self.__instrument_loader_task = self.event_loop.create_task(
            self.__instrumentLoader())
        self.__instrument_loader_task.add_done_callback(self.__instrument_loader_done)

    async def cleanup(self) -> None:
        logger.info("Cleaning up instrument library dialog...")

        async with self.__instrument_lock:
            if self.__instrument_loader_task is not None:
                self.__instrument_loader_task.cancel()
                self.__instrument_loader_task = None

            if self.__instrument_id is not None:
                await self.audioproc_client.disconnect_ports(
                    'root',
                    self.__instrument_id, 'out:left', 'sink', 'in:left')
                await self.audioproc_client.disconnect_ports(
                    'root',
                    self.__instrument_id, 'out:right', 'sink', 'in:right')

                if self.__midi_source_id is not None:
                    await self.audioproc_client.disconnect_ports(
                        'root',
                        self.__midi_source_id, 'out', self.__instrument_id, 'in')

            if self.__midi_source_id is not None:
                await self.audioproc_client.remove_node(
                    'root', self.__midi_source_id)
                self.__midi_source_id = None

            if self.__instrument_id is not None:
                await self.audioproc_client.remove_node(
                    'root', self.__instrument_id)
                self.__instrument_id = None

    async def __instrumentLoader(self) -> None:
        while True:
            description = await self.__instrument_queue.get()
            while True:
                try:
                    description = self.__instrument_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            async with self.__instrument_lock:
                self.piano.setEnabled(False)
                self.spinner.setVisible(True)

                self.instrument_name.setText(description.display_name)
                self.instrument_data.setPlainText(str(description))

                try:
                    instrument_spec = instrument_db.create_instrument_spec(description.uri)
                except instrument_db.InvalidInstrumentURI as exc:
                    logger.error("Invalid instrument URI '%s': %s", description.uri, exc)
                else:
                    await self.sendNodeMessage(instrument.change_instrument(
                        self.__instrument_id, instrument_spec))

                self.piano.setEnabled(True)
                self.spinner.setVisible(False)

                self.__instrument = description
                self.instrumentChanged.emit(description)

    def __instrument_loader_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        task.result()

    def onRescan(self) -> None:
        self.call_async(self.app.instrument_db.start_scan())

    def selectInstrument(self, uri: str) -> None:
        for instr in self.app.instrument_list.instruments():
            if instr.description.uri == uri:
                index = self.app.instrument_list.indexForItem(instr)
                index = self.__model_filter.mapFromSource(index)
                self.__view.setCurrentIndex(index)

    def onInstrumentItemSelected(self, index: QtCore.QModelIndex) -> None:
        index = self.__model_filter.mapToSource(index)
        item = self.app.instrument_list.item(index)
        if item is not None and isinstance(item, instrument_list.Instrument):
            self.__instrument_queue.put_nowait(item.description)

    def onInstrumentSearchChanged(self, text: str) -> None:
        self.__model_filter.setFilter(text)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        self.piano.keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        self.piano.keyReleaseEvent(event)

    async def sendNodeMessage(self, msg: audioproc.ProcessorMessage) -> None:
        await self.audioproc_client.send_node_messages(
            'root', audioproc.ProcessorMessageList(messages=[msg]))

    def onNoteOn(self, pitch: value_types.Pitch) -> None:
        if self.__midi_source_id is not None:
            self.call_async(self.sendNodeMessage(
                midi_source.note_on_event(
                    self.__midi_source_id, 0, pitch.midi_note, 100)))

    def onNoteOff(self, pitch: value_types.Pitch) -> None:
        if self.__midi_source_id is not None:
            self.call_async(self.sendNodeMessage(
                midi_source.note_off_event(
                    self.__midi_source_id, 0, pitch.midi_note)))
