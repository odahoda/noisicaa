#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import logging
import os.path

from PyQt5.QtCore import Qt, QByteArray, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from .piano import PianoWidget
from ..constants import DATA_DIR
from ..instr.library import (
    SampleInstrument,
    SoundFontInstrument,
    Instrument,
    InstrumentLibrary,
)
from ..audioproc.source.fluidsynth import FluidSynthSource
from ..ui_state import UpdateUIState


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

class InstrumentListItem(QListWidgetItem):
    def __init__(self, parent, instrument):
        super().__init__(parent, 0)
        self.instrument = instrument


class InstrumentLibraryDialog(QDialog):
    instrumentChanged = pyqtSignal(Instrument)

    def __init__(self, parent, app, library):
        super().__init__(parent)

        logger.info("InstrumentLibrary created")
        self._app = app

        self.library = library
        self.ui_state = self.library.ui_state
        self.ui_state.add_change_listener(self.onUIStateChange)

        self.player_source = None

        self.setWindowTitle("noisicaä - Instrument Library")

        self.tabs = QTabWidget(self)

        self.instruments_page = QSplitter(self.tabs)
        self.instruments_page.setChildrenCollapsible(False)

        left = QWidget(self)
        self.instruments_page.addWidget(left)

        layout = QVBoxLayout()
        left.setLayout(layout)

        self.instruments_search = QLineEdit(self)
        layout.addWidget(self.instruments_search)
        self.instruments_search.addAction(QIcon.fromTheme('edit-find'), QLineEdit.LeadingPosition)
        action = QAction(QIcon.fromTheme('edit-clear'), "Clear search string", self.instruments_search, triggered=self.instruments_search.clear)
        self.instruments_search.addAction(action, QLineEdit.TrailingPosition)
        self.instruments_search.textChanged.connect(self.onInstrumentSearchChanged)

        self.instruments_list = instrument_list = QListWidget(self)
        layout.addWidget(instrument_list, 1)
        instrument_list.currentItemChanged.connect(
            lambda current, prev: self.onInstrumentItemSelected(current))

        buttons = QHBoxLayout()
        layout.addLayout(buttons)

        add_button = QPushButton("Add")
        add_button.clicked.connect(self.onInstrumentAdd)
        buttons.addWidget(add_button)
        buttons.addWidget(QPushButton("Remove"))
        buttons.addStretch(1)

        instrument_info = QWidget(self)
        self.instruments_page.addWidget(instrument_info)

        layout = QVBoxLayout()
        instrument_info.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self.instrument_name = QLineEdit(self, readOnly=True)
        form_layout.addRow("Name", self.instrument_name)

        self.instrument_type = QLineEdit(self, readOnly=True)
        form_layout.addRow("Type", self.instrument_type)

        self.instrument_path = QLineEdit(self, readOnly=True)
        form_layout.addRow("Path", self.instrument_path)

        self.instrument_collection = QLineEdit(self, readOnly=True)
        form_layout.addRow("Collection", self.instrument_collection)

        self.instrument_location = QLineEdit(self, readOnly=True)
        form_layout.addRow("Location", self.instrument_location)

        layout.addStretch(1)

        self.piano = PianoWidget(self, self._app)
        self.piano.setVisible(False)
        self.piano.noteOn.connect(self.onNoteOn)
        self.piano.noteOff.connect(self.onNoteOff)
        layout.addWidget(self.piano)

        self.tabs.addTab(self.instruments_page, "Instruments")

        collections_page = QWidget(self.tabs)
        layout = QVBoxLayout()

        layout.addStretch(1)
        collections_page.setLayout(layout)

        self.tabs.addTab(collections_page, "Collections")


        close = QPushButton("Close")
        close.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout()
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.updateInstrumentList()

        self.setVisible(
            self.ui_state.get('visible', False))
        self.restoreGeometry(
            QByteArray(self.ui_state.get('geometry', b'')))
        self.tabs.setCurrentIndex(
            self.ui_state.get('page', 0))
        self.instruments_page.restoreState(
            self.ui_state.get('instruments_splitter_state', b''))
        self.instruments_list.setCurrentRow(
            self.ui_state.get('instruments_list_item', 0))
        self.instruments_search.setText(
            self.ui_state.get('instruments_search_text', ''))

    def closeEvent(self, event):
        self.library.dispatch_command(
            "/ui_state",
            UpdateUIState(
                visible=False,
                geometry=bytes(self.saveGeometry()),
                page=self.tabs.currentIndex(),
                instruments_splitter_state=bytes(
                    self.instruments_page.saveState()),
                instruments_list_item=self.instruments_list.currentRow(),
                instruments_search_text=self.instruments_search.text(),
            ))
        if self.player_source is not None:
            self._app.removePlaybackSource(self.player_source.outputs['out'])
            self.player_source.cleanup()
            self.player_source = None

    def updateInstrumentList(self):
        self.instruments_list.clear()
        for idx, instr in enumerate(self.library.instruments):
            item = InstrumentListItem(self.instruments_list, instr)
            item.setText(instr.name)
            self.instruments_list.addItem(item)

    def selectInstrument(self, instr):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if item.instrument == instr:
                self.instruments_list.setCurrentRow(idx)
                break

    def onUIStateChange(self, changes):
        logger.info("onUIStateChange(%r)", changes)
        for key, value in changes.items():
            if key == 'visible':
                if value:
                    self.restoreGeometry(
                        QByteArray(self.ui_state.get('geometry', b'')))
                    self.show()
                    self.activateWindow()
                else:
                    self.hide()

    def onInstrumentItemSelected(self, item):
        if self.player_source is not None:
            self._app.removePlaybackSource(self.player_source.outputs['out'])
            self.player_source.cleanup()
            self.player_source = None

        if item is None:
            self.instrument_name.setText("")
            self.instrument_collection.setText("")
            self.instrument_type.setText("")
            self.instrument_path.setText("")
            self.instrument_location.setText("")
            return

        instr = item.instrument

        self.instrument_name.setText(instr.name)

        if instr.collection is not None:
            self.instrument_collection.setText(instr.collection.name)
        else:
            self.instrument_collection.setText("")

        if isinstance(instr, SampleInstrument):
            self.instrument_type.setText("Sample")
            self.instrument_path.setText(instr.path)
            self.instrument_location.setText("")

        elif isinstance(instr, SoundFontInstrument):
            self.instrument_type.setText("SoundFont")
            self.instrument_path.setText("")
            self.instrument_location.setText(
                "bank %d, preset %d" % (instr.bank, instr.preset))

            self.player_source = FluidSynthSource(
                instr.path, instr.bank, instr.preset)
            self.player_source.setup()
            self._app.addPlaybackSource(self.player_source.outputs['out'])

        if self.player_source is not None:
            self.piano.setVisible(True)
            self.piano.setFocus(Qt.OtherFocusReason)
        else:
            self.piano.setVisible(False)

        self.instrumentChanged.emit(instr)

    def onInstrumentSearchChanged(self, text):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def onInstrumentAdd(self):
        path, open_filter = QFileDialog.getOpenFileName(
            parent=self,
            caption="Open Project",
            directory=self.ui_state.get(
                'instruments_add_dialog_path', ''),
            filter="All Files (*);;SoundFont Files (*.sf2)",
            initialFilter=self.ui_state.get(
                'instruments_add_dialog_path', ''))
        if not path:
            return

        self.library.dispatch_command(
            "/ui_state",
            UpdateUIState(
                instruments_add_dialog_path=path,
                instruments_add_dialog_filter=open_filter,
            ))

        self.library.add_soundfont(path)
        self.updateInstrumentList()

    def keyPressEvent(self, event):
        self.piano.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.piano.keyReleaseEvent(event)

    def onNoteOn(self, note, volume):
        if self.player_source is not None:
            self.player_source.note_on(note, volume)

    def onNoteOff(self, note):
        if self.player_source is not None:
            self.player_source.note_off(note)
