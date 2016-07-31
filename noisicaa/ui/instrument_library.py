#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import asyncio
import logging
import os.path

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from .piano import PianoWidget
from ..constants import DATA_DIR
from . import ui_base
from ..instr import library

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
    def __init__(self, parent, instrument):
        super().__init__(parent, 0)
        self.instrument = instrument


class InstrumentLibraryDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    instrumentChanged = QtCore.pyqtSignal(library.Instrument)

    def __init__(self, parent=None, selectButton=False, **kwargs):
        super().__init__(parent=parent, **kwargs)

        logger.info("InstrumentLibrary created")

        self._pipeline_lock = asyncio.Lock()
        self._pipeline_mixer_id = None
        self._pipeline_instrument_id = None

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

        buttons = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons)

        add_button = QtWidgets.QPushButton("Add")
        add_button.clicked.connect(self.onInstrumentAdd)
        buttons.addWidget(add_button)
        buttons.addWidget(QtWidgets.QPushButton("Remove"))
        buttons.addStretch(1)

        instrument_info = QtWidgets.QWidget(self)
        self.instruments_page.addWidget(instrument_info)

        layout = QtWidgets.QVBoxLayout()
        instrument_info.setLayout(layout)

        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.instrument_name = QtWidgets.QLineEdit(self, readOnly=True)
        form_layout.addRow("Name", self.instrument_name)

        self.instrument_type = QtWidgets.QLineEdit(self, readOnly=True)
        form_layout.addRow("Type", self.instrument_type)

        self.instrument_path = QtWidgets.QLineEdit(self, readOnly=True)
        form_layout.addRow("Path", self.instrument_path)

        self.instrument_collection = QtWidgets.QLineEdit(self, readOnly=True)
        form_layout.addRow("Collection", self.instrument_collection)

        self.instrument_location = QtWidgets.QLineEdit(self, readOnly=True)
        form_layout.addRow("Location", self.instrument_location)

        layout.addStretch(1)

        self.piano = PianoWidget(self, self.app)
        self.piano.setVisible(False)
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

        self.updateInstrumentList()

    @property
    def library(self):
        return self.app.instrument_library

    def instrument(self):
        return self._instrument

    async def setup(self):
        logger.info("Setting up instrument library dialog...")

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

    async def addInstrumentToPipeline(self, node_type, **args):
        assert self._pipeline_instrument_id is None

        self._pipeline_instrument_id = await self.audioproc_client.add_node(
            node_type, **args)
        await self.audioproc_client.connect_ports(
            self._pipeline_instrument_id, 'out',
            self._pipeline_mixer_id, 'in')

        self._pipeline_event_source_id = await self.audioproc_client.add_node(
            'track_event_source')
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

    def updateInstrumentList(self):
        self.instruments_list.clear()
        for idx, instr in enumerate(self.library.instruments):
            item = InstrumentListItem(self.instruments_list, instr)
            item.setText(instr.name)
            self.instruments_list.addItem(item)

    def selectInstrument(self, instr_id):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if item.instrument.id == instr_id:
                self.instruments_list.setCurrentRow(idx)
                break

    def onInstrumentItemSelected(self, item):
        if item is None:
            self.instrument_name.setText("")
            self.instrument_collection.setText("")
            self.instrument_type.setText("")
            self.instrument_path.setText("")
            self.instrument_location.setText("")
            return

        self.call_async(self.setCurrentInstrument(item.instrument))

    async def setCurrentInstrument(self, instr):
        await self.removeInstrumentFromPipeline()

        self.instrument_name.setText(instr.name)

        if instr.collection is not None:
            self.instrument_collection.setText(instr.collection.name)
        else:
            self.instrument_collection.setText("")

        if isinstance(instr, library.SoundFontInstrument):
            self.instrument_type.setText("SoundFont")
            self.instrument_path.setText(instr.path)
            self.instrument_location.setText(
                "bank %d, preset %d" % (instr.bank, instr.preset))

            await self.addInstrumentToPipeline(
                'fluidsynth',
                soundfont_path=instr.path,
                bank=instr.bank, preset=instr.preset)

        #self.piano.setVisible(True)
        #self.piano.setFocus(Qt.OtherFocusReason)

        self._instrument = instr
        self.instrumentChanged.emit(instr)

    def onInstrumentSearchChanged(self, text):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def onInstrumentAdd(self):
        # TODO: persists directory/filter in app settings.
        path, open_filter = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Open Project",
            # directory=self.ui_state.get(
            #     'instruments_add_dialog_path', ''),
            filter="All Files (*);;SoundFont Files (*.sf2)",
            # initialFilter=self.ui_state.get(
            #     'instruments_add_dialog_path', '')
        )
        if not path:
            return

        self.library.add_soundfont(path)
        self.updateInstrumentList()

    def keyPressEvent(self, event):
        self.piano.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.piano.keyReleaseEvent(event)
