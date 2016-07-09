#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import logging
import os.path

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from .piano import PianoWidget
from ..constants import DATA_DIR
#from ..ui_state import UpdateUIState
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

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)

        logger.info("InstrumentLibrary created")

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

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.updateInstrumentList()

        # self.setVisible(
        #     self.ui_state.get('visible', False))
        # self.restoreGeometry(
        #     QtCore.QByteArray(self.ui_state.get('geometry', b'')))
        # self.tabs.setCurrentIndex(
        #     self.ui_state.get('page', 0))
        # self.instruments_page.restoreState(
        #     self.ui_state.get('instruments_splitter_state', b''))
        # self.instruments_list.setCurrentRow(
        #     self.ui_state.get('instruments_list_item', 0))
        # self.instruments_search.setText(
        #     self.ui_state.get('instruments_search_text', ''))

    @property
    def library(self):
        return self.app.instrument_library

    # def closeEvent(self, event):
    #     self.library.dispatch_command(
    #         "/ui_state",
    #         UpdateUIState(
    #             visible=False,
    #             geometry=bytes(self.saveGeometry()),
    #             page=self.tabs.currentIndex(),
    #             instruments_splitter_state=bytes(
    #                 self.instruments_page.saveState()),
    #             instruments_list_item=self.instruments_list.currentRow(),
    #             instruments_search_text=self.instruments_search.text(),
    #         ))

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

    # def onUIStateChange(self, changes):
    #     logger.info("onUIStateChange(%r)", changes)
    #     for key, value in changes.items():
    #         if key == 'visible':
    #             if value:
    #                 self.restoreGeometry(
    #                     QtCore.QByteArray(self.ui_state.get('geometry', b'')))
    #                 self.show()
    #                 self.activateWindow()
    #             else:
    #                 self.hide()

    def onInstrumentItemSelected(self, item):
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

        if isinstance(instr, library.SoundFontInstrument):
            self.instrument_type.setText("SoundFont")
            self.instrument_path.setText(instr.path)
            self.instrument_location.setText(
                "bank %d, preset %d" % (instr.bank, instr.preset))

        self.piano.setVisible(True)
        self.piano.setFocus(Qt.OtherFocusReason)

        self.instrumentChanged.emit(instr)

    def onInstrumentSearchChanged(self, text):
        for idx in range(self.instruments_list.count()):
            item = self.instruments_list.item(idx)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def onInstrumentAdd(self):
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

        # self.library.dispatch_command(
        #     "/ui_state",
        #     UpdateUIState(
        #         instruments_add_dialog_path=path,
        #         instruments_add_dialog_filter=open_filter,
        #     ))

        self.library.add_soundfont(path)
        self.updateInstrumentList()

    def keyPressEvent(self, event):
        self.piano.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.piano.keyReleaseEvent(event)
