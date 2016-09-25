#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import asyncio
import logging
import pprint

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import instrument_db

from .piano import PianoWidget
from . import ui_base

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

class InstrumentListItem(QtWidgets.QListWidgetItem):
    def __init__(self, parent, description):
        super().__init__(parent, 0)
        self.description = description
        self.setText(description.display_name)


class InstrumentLibraryDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    instrumentChanged = QtCore.pyqtSignal(instrument_db.InstrumentDescription)

    def __init__(self, parent=None, selectButton=False, **kwargs):
        super().__init__(parent=parent, **kwargs)

        logger.info("InstrumentLibrary created")

        self._pipeline_lock = asyncio.Lock()
        self._pipeline_mixer_id = None
        self._pipeline_instrument_id = None
        self._pipeline_event_source_id = None

        self.instrument_mutation_listener = None

        self._instrument = None

        self.setWindowTitle("noisicaä - Instrument Library")

        self.tabs = QtWidgets.QTabWidget(self)

        self.instruments_page = QtWidgets.QSplitter(self.tabs)
        self.instruments_page.setChildrenCollapsible(False)

        left = QtWidgets.QWidget(self)
        self.instruments_page.addWidget(left)

        layout = QtWidgets.QVBoxLayout()
        left.setLayout(layout)

        self.instruments_search = QtWidgets.QLineEdit(self)
        layout.addWidget(self.instruments_search)
        self.instruments_search.addAction(QtGui.QIcon.fromTheme('edit-find'), QtWidgets.QLineEdit.LeadingPosition)
        action = QtWidgets.QAction(QtGui.QIcon.fromTheme('edit-clear'), "Clear search string", self.instruments_search, triggered=self.instruments_search.clear)
        self.instruments_search.addAction(action, QtWidgets.QLineEdit.TrailingPosition)
        self.instruments_search.textChanged.connect(self.onInstrumentSearchChanged)

        self.instruments_list = instrument_list = QtWidgets.QListWidget(self)
        layout.addWidget(instrument_list, 1)
        instrument_list.currentItemChanged.connect(
            lambda current, prev: self.onInstrumentItemSelected(current))

        instrument_info = QtWidgets.QWidget(self)
        self.instruments_page.addWidget(instrument_info)

        layout = QtWidgets.QVBoxLayout()
        instrument_info.setLayout(layout)

        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.instrument_name = QtWidgets.QLineEdit(self, readOnly=True)
        form_layout.addRow("Name", self.instrument_name)

        self.instrument_data = QtWidgets.QTextEdit(self, readOnly=True)
        form_layout.addRow("Description", self.instrument_data)

        layout.addStretch(1)

        self.piano = PianoWidget(self, self.app)
        self.piano.setVisible(False)
        self.piano.noteOn.connect(self.onNoteOn)
        self.piano.noteOff.connect(self.onNoteOff)
        layout.addWidget(self.piano)

        self.tabs.addTab(self.instruments_page, "Instruments")

        collections_page = QtWidgets.QWidget(self.tabs)
        layout = QtWidgets.QVBoxLayout()

        layout.addStretch(1)
        collections_page.setLayout(layout)

        self.tabs.addTab(collections_page, "Collections")


        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)

        if selectButton:
            select = QtWidgets.QPushButton("Select")
            select.clicked.connect(self.accept)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        if selectButton:
            buttons.addWidget(select)
        buttons.addWidget(close)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

    @property
    def library(self):
        return self.app.instrument_library

    def instrument(self):
        return self._instrument

    async def setup(self):
        logger.info("Setting up instrument library dialog...")

        self.instruments_list.clear()
        for description in self.app.instrument_db.instruments:
            self.instruments_list.addItem(
                InstrumentListItem(self.instruments_list, description))
        self._instrument_mutation_listener = self.app.instrument_db.listeners.add(
            'mutation', self.handleInstrumentMutation)

        self._pipeline_mixer_id = await self.audioproc_client.add_node(
            'passthru', name='library-mixer')
        await self.audioproc_client.connect_ports(
            self._pipeline_mixer_id, 'out', 'sink', 'in')

    async def cleanup(self):
        logger.info("Cleaning up instrument library dialog...")

        if self._pipeline_instrument_id is not None:
            assert self._pipeline_mixer_id is not None
            await self.removeInstrumentFromPipeline()

        if self._pipeline_mixer_id is not None:
            await self.audioproc_client.disconnect_ports(
                self._pipeline_mixer_id, 'out', 'sink', 'in')
            await self.audioproc_client.remove_node(
                self._pipeline_mixer_id)
            self._pipeline_mixer_id = None

        if self._instrument_mutation_listener is not None:
            self._instrument_mutation_listener.remove()
            self._instrument_mutation_listener = None

    def handleInstrumentMutation(self, mutation):
        logger.info("Mutation received: %s", mutation)
        description = mutation.description
        self.instruments_list.addItem(
            InstrumentListItem(self.instruments_list, description))

    async def addInstrumentToPipeline(self, uri):
        assert self._pipeline_instrument_id is None

        node_cls, node_args = instrument_db.parse_uri(uri)
        self._pipeline_instrument_id = await self.audioproc_client.add_node(
            node_cls, **node_args)
        await self.audioproc_client.connect_ports(
            self._pipeline_instrument_id, 'out',
            self._pipeline_mixer_id, 'in')

        self._pipeline_event_source_id = await self.audioproc_client.add_node(
            'track_event_source', queue_name='instrument_library')
        await self.audioproc_client.connect_ports(
            self._pipeline_event_source_id, 'out',
            self._pipeline_instrument_id, 'in')

    async def removeInstrumentFromPipeline(self):
        async with self._pipeline_lock:
            if self._pipeline_instrument_id is None:
                return

            await self.audioproc_client.disconnect_ports(
                self._pipeline_event_source_id, 'out',
                self._pipeline_instrument_id, 'in')
            await self.audioproc_client.remove_node(
                self._pipeline_event_source_id)
            self._pipeline_event_source_id = None

            await self.audioproc_client.disconnect_ports(
                self._pipeline_instrument_id, 'out',
                self._pipeline_mixer_id, 'in')
            await self.audioproc_client.remove_node(
                self._pipeline_instrument_id)
            self._pipeline_instrument_id = None

    def closeEvent(self, event):
        if self._pipeline_instrument_id is not None:
            self.call_async(self.removeInstrumentFromPipeline())

        super().closeEvent(event)

    def selectInstrument(self, uri):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if item.description.uri == uri:
                self.instruments_list.setCurrentRow(idx)
                break

    def onInstrumentItemSelected(self, item):
        if item is None:
            self.instrument_name.setText("")
            self.instrument_data.setText("")
            return

        self.call_async(self.setCurrentInstrument(item.description))

    async def setCurrentInstrument(self, description):
        await self.removeInstrumentFromPipeline()

        self.instrument_name.setText(description.display_name)
        self.instrument_data.setPlainText(pprint.pformat(description.properties))

        await self.addInstrumentToPipeline(description.uri)

        self.piano.setVisible(True)
        self.piano.setFocus(Qt.OtherFocusReason)

        self._instrument = description
        self.instrumentChanged.emit(description)

    def onInstrumentSearchChanged(self, text):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def keyPressEvent(self, event):
        self.piano.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.piano.keyReleaseEvent(event)

    def onNoteOn(self, note, volume):
        if self._pipeline_event_source_id is not None:
            self.call_async(
                self.audioproc_client.add_event(
                    'instrument_library',
                    audioproc.NoteOnEvent(-1, note, volume)))


    def onNoteOff(self, note):
        if self._pipeline_event_source_id is not None:
            self.call_async(
                self.audioproc_client.add_event(
                    'instrument_library',
                    audioproc.NoteOffEvent(-1, note)))
