#!/usr/bin/python

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import asyncio
import bisect
import logging
import pathlib
import pprint
import uuid

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import instrument_db
from noisicaa import node_db

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


class Item(object):
    def __init__(self, *, parent):
        self.parent = parent

    def __lt__(self, other):
        return self.key < other.key

    @property
    def key(self):
        raise NotImplementedError

    @property
    def display_name(self):
        raise NotImplementedError

    def walk(self):
        yield self


class AbstractFolder(Item):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.children = []

    def walk(self):
        yield from super().walk()
        for child in self.children:
            yield from child.walk()


class Root(AbstractFolder):
    def __init__(self):
        super().__init__(parent=None)

    @property
    def key(self):
        return (0, str(self.path).lower(), str(self.path))

    @property
    def display_name(self):
        return '[root]'


class Folder(AbstractFolder):
    def __init__(self, *, path, **kwargs):
        super().__init__(**kwargs)

        self.path = path

    @property
    def key(self):
        return (0, str(self.path).lower(), str(self.path))

    @property
    def display_name(self):
        return str(self.path)


class Instrument(Item):
    def __init__(self, *, description, **kwargs):
        super().__init__(**kwargs)
        self.description = description

    @property
    def key(self):
        return (0, self.description.display_name.lower(), self.description.uri)

    @property
    def display_name(self):
        return self.description.display_name


class LibraryModelImpl(QtCore.QAbstractItemModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__root_item = Root()

    def close(self):
        self.__root_item = None

    def clear(self):
        self.__root_item = Root()

    def addInstrument(self, description):
        parent = self.__root_item
        parent_index = self.indexForItem(parent)

        if description.format == 'sf2':
            folder_path = pathlib.Path(description.path)
        else:
            folder_path = pathlib.Path(description.path).parent

        folder_parts = folder_path.parts
        assert len(folder_parts) > 0, description.path
        while folder_parts:
            for folder_idx, folder in enumerate(parent.children):
                if not isinstance(folder, AbstractFolder):
                    continue

                match_length = 0
                for idx, part in enumerate(folder.path.parts):
                    if part != folder_parts[idx]:
                        break
                    match_length += 1

                if match_length > 0:
                    break

            else:
                folder = Folder(path=pathlib.Path(*folder_parts), parent=parent)
                match_length = len(folder_parts)
                folder_idx = bisect.bisect(parent.children, folder)
                self.beginInsertRows(parent_index, folder_idx, folder_idx)
                parent.children.insert(folder_idx, folder)
                self.endInsertRows()

            assert folder_parts[:match_length] == folder.path.parts[:match_length]

            if match_length < len(folder.path.parts):
                self.beginRemoveRows(parent_index, folder_idx, folder_idx)
                old_folder = parent.children.pop(folder_idx)
                self.endRemoveRows()

                folder = Folder(path=pathlib.Path(*folder_parts[:match_length]), parent=parent)
                folder_idx = bisect.bisect(parent.children, folder)
                self.beginInsertRows(parent_index, folder_idx, folder_idx)
                parent.children.insert(folder_idx, folder)
                self.endInsertRows()

                new_folder = Folder(path=pathlib.Path(
                    *old_folder.path.parts[match_length:]), parent=folder)
                for child in old_folder.children:
                    child.parent = new_folder
                    new_folder.children.append(child)
                new_folder_idx = bisect.bisect(folder.children, folder)
                self.beginInsertRows(self.indexForItem(folder), new_folder_idx, new_folder_idx)
                folder.children.insert(folder_idx, new_folder)
                self.endInsertRows()

            folder_parts = folder_parts[match_length:]

            parent = folder
            parent_index = self.indexForItem(folder)

        instr = Instrument(
            description=description,
            parent=parent)
        insert_pos = bisect.bisect(parent.children, instr)

        self.beginInsertRows(parent_index, insert_pos, insert_pos)
        parent.children.insert(insert_pos, instr)
        self.endInsertRows()

    def instruments(self):
        for item in self.__root_item.walk():
            if isinstance(item, Instrument):
                yield item

    def flattened(self, parent=None):
        if parent is None:
            parent = self.__root_item

        path = []
        folder = parent
        while folder.parent is not None:
            path.insert(0, folder.display_name)
            folder = folder.parent

        if path:
            yield path

        for item in parent.children:
            if isinstance(item, Instrument):
                yield path + [item.display_name]
            elif isinstance(item, AbstractFolder):
                yield from self.flattened(item)

    def item(self, index):
        if not index.isValid():
            raise ValueError("Invalid index")

        item = index.internalPointer()
        assert item is not None
        return item

    def indexForItem(self, item, column=0):
        if item.parent is None:
            return QtCore.QModelIndex()
        else:
            return self.createIndex(
                item.parent.children.index(item), column, item)

    def rowCount(self, parent):
        if parent.column() > 0:  # pragma: no coverage
            return 0

        if not parent.isValid():
            return len(self.__root_item.children)

        parent_item = parent.internalPointer()
        if parent_item is None:
            return 0

        if isinstance(parent_item, AbstractFolder):
            return len(parent_item.children)
        else:
            return 0

    def columnCount(self, parent):
        return 1

    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):  # pragma: no coverage
            return QtCore.QModelIndex()

        if not parent.isValid():
            return self.createIndex(row, column, self.__root_item.children[row])

        parent_item = parent.internalPointer()
        assert isinstance(parent_item, AbstractFolder), parent_item.track

        item = parent_item.children[row]
        return self.createIndex(row, column, item)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        item = index.internalPointer()
        if item is None or item.parent is None:
            return QtCore.QModelIndex()

        return self.indexForItem(item.parent)

    def data(self, index, role):
        if not index.isValid():  # pragma: no coverage
            return None

        item = index.internalPointer()
        if item is None:
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column() == 0:
                return item.display_name

        return None  # pragma: no coverage

    def headerData(self, section, orientation, role):  # pragma: no coverage
        return None


class LibraryModel(ui_base.CommonMixin, LibraryModelImpl):
    pass


class FilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, source, **kwargs):
        super().__init__(**kwargs)

        self.setSourceModel(source)

        self.__source = source
        self.__filter = ''

    def setFilter(self, text):
        words = text.split()
        words = [word.strip() for word in words]
        words = [word for word in words if word]
        words = [word.lower() for word in words]
        self.__filter = words
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        if not self.__filter:
            return True

        if not parent.isValid():
            return True

        parent_item = self.__source.item(parent)
        item = parent_item.children[row]

        if isinstance(item, AbstractFolder):
            # Urgh... this is O(n^2)
            folder_index = self.__source.index(row, 0, parent)
            return any(
                self.filterAcceptsRow(subrow, folder_index)
                for subrow in range(len(item.children)))

        return all(word in item.display_name.lower() for word in self.__filter)


class LibraryView(QtWidgets.QTreeView):
    currentIndexChanged = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderHidden(True)
        self.setMinimumWidth(250)

    def currentChanged(self, current, previous):
        self.currentIndexChanged.emit(current)

    def contextMenuEvent(self, evt):
        menu = QtWidgets.QMenu()

        expand_all = menu.addAction("Expand all")
        expand_all.triggered.connect(self.expandAll)

        collaps_all = menu.addAction("Collaps all")
        collaps_all.triggered.connect(self.collapseAll)

        menu.exec_(evt.globalPos())
        evt.accept()


class InstrumentLibraryDialog(ui_base.CommonMixin, QtWidgets.QDialog):
    instrumentChanged = QtCore.pyqtSignal(instrument_db.InstrumentDescription)

    def __init__(self, parent=None, selectButton=False, **kwargs):
        super().__init__(parent=parent, **kwargs)

        logger.info("InstrumentLibrary created")

        self._pipeline_lock = asyncio.Lock()
        self._pipeline_mixer_id = None
        self._pipeline_instrument_id = None
        self._pipeline_event_source_id = None

        self._instrument_mutation_listener = None

        self._instrument = None

        self.setWindowTitle("noisicaä - Instrument Library")

        menubar = QtWidgets.QMenuBar(self)
        library_menu = menubar.addMenu("Library")

        rescan_action = QtWidgets.QAction(
            "Rescan", self,
            statusTip="Rescan library for updates.",
            triggered=self.onRescan)
        library_menu.addAction(rescan_action)

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

        self.__model = LibraryModel(**self.context)
        self.__model_filter = FilterModel(self.__model)
        self.__view = LibraryView(self)
        self.__view.setModel(self.__model_filter)
        layout.addWidget(self.__view, 1)
        self.__view.currentIndexChanged.connect(self.onInstrumentItemSelected)

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
        layout.setMenuBar(menubar)
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

        self.__model.clear()
        for description in self.app.instrument_db.instruments:
            self.__model.addInstrument(description)

        self._instrument_mutation_listener = self.app.instrument_db.listeners.add(
            'mutation', self.handleInstrumentMutation)

        self._pipeline_mixer_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            description=node_db.TrackMixerDescription,
            id=self._pipeline_mixer_id,
            name='library-mixer')
        await self.audioproc_client.connect_ports(
            self._pipeline_mixer_id, 'out:left', 'sink', 'in:left')
        await self.audioproc_client.connect_ports(
            self._pipeline_mixer_id, 'out:right', 'sink', 'in:right')

    async def cleanup(self):
        logger.info("Cleaning up instrument library dialog...")

        if self._pipeline_instrument_id is not None:
            assert self._pipeline_mixer_id is not None
            await self.removeInstrumentFromPipeline()

        if self._pipeline_mixer_id is not None:
            await self.audioproc_client.disconnect_ports(
                self._pipeline_mixer_id, 'out:left', 'sink', 'in:left')
            await self.audioproc_client.disconnect_ports(
                self._pipeline_mixer_id, 'out:right', 'sink', 'in:right')
            await self.audioproc_client.remove_node(
                self._pipeline_mixer_id)
            self._pipeline_mixer_id = None

        if self._instrument_mutation_listener is not None:
            self._instrument_mutation_listener.remove()
            self._instrument_mutation_listener = None

    def handleInstrumentMutation(self, mutation):
        logger.info("Mutation received: %s", mutation)
        self.__model.addInstrument(mutation.description)

    async def addInstrumentToPipeline(self, uri):
        assert self._pipeline_instrument_id is None

        node_uri, node_params = instrument_db.parse_uri(uri)
        self._pipeline_instrument_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            description=self.app.node_db.get_node_description(node_uri),
            id=self._pipeline_instrument_id,
            initial_parameters=node_params)
        await self.audioproc_client.connect_ports(
            self._pipeline_instrument_id, 'out:left',
            self._pipeline_mixer_id, 'in:left')
        await self.audioproc_client.connect_ports(
            self._pipeline_instrument_id, 'out:right',
            self._pipeline_mixer_id, 'in:right')

        self._pipeline_event_source_id = uuid.uuid4().hex
        await self.audioproc_client.add_node(
            description=node_db.EventSourceDescription,
            id=self._pipeline_event_source_id,
            track_id='instrument_library')
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
                self._pipeline_instrument_id, 'out:left',
                self._pipeline_mixer_id, 'in:left')
            await self.audioproc_client.disconnect_ports(
                self._pipeline_instrument_id, 'out:right',
                self._pipeline_mixer_id, 'in:right')
            await self.audioproc_client.remove_node(
                self._pipeline_instrument_id)
            self._pipeline_instrument_id = None

    def closeEvent(self, event):
        if self._pipeline_instrument_id is not None:
            self.call_async(self.removeInstrumentFromPipeline())

        super().closeEvent(event)

    def onRescan(self):
        self.call_async(self.app.instrument_db.start_scan())

    def selectInstrument(self, uri):
        for instr in self.__model.instruments():
            if instr.description.uri == uri:
                index = self.__model.indexForItem(instr)
                index = self.__model_filter.mapFromSource(index)
                self.__view.setCurrentIndex(index)

    def onInstrumentItemSelected(self, index):
        index = self.__model_filter.mapToSource(index)
        item = self.__model.item(index)
        if item is None or not isinstance(item, Instrument):
            self.instrument_name.setText("")
            self.instrument_data.setText("")
            return

        self.call_async(self.setCurrentInstrument(item.description))

    async def setCurrentInstrument(self, description):
        await self.removeInstrumentFromPipeline()

        self.instrument_name.setText(description.display_name)
        self.instrument_data.setPlainText("""\
uri: {uri}
properties: {properties}
            """.format(
                uri=description.uri,
                properties=pprint.pformat(description.properties)))

        await self.addInstrumentToPipeline(description.uri)

        self.piano.setVisible(True)
        self.piano.setFocus(Qt.OtherFocusReason)

        self._instrument = description
        self.instrumentChanged.emit(description)

    def onInstrumentSearchChanged(self, text):
        self.__model_filter.setFilter(text)

    def keyPressEvent(self, event):
        self.piano.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.piano.keyReleaseEvent(event)

    def onNoteOn(self, note, volume):
        if self._pipeline_event_source_id is not None:
            # self.call_async(
            #     self.project_client.player_send_message(
            #         self.playerState().playerID(),
            #         core.build_message(
            #             {core.MessageKey.sheetId: self.sheet.id,
            #              core.MessageKey.trackId: 'instrument_library'},
            #             core.MessageType.atom,
            #             lv2.AtomForge.build_midi_noteon(0, note, volume))))
            pass

    def onNoteOff(self, note):
        if self._pipeline_event_source_id is not None:
            # TODO: use messages instead
            # self.call_async(
            #     self.audioproc_client.add_event(
            #         'instrument_library',
            #         audioproc.NoteOffEvent(-1, note)))
            pass
