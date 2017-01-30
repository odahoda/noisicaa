#!/usr/bin/python3

import os.path
import unittest
from unittest import mock

from PyQt5.QtCore import Qt
from PyQt5 import QtCore

from noisicaa import instrument_db
from . import uitest_utils
from . import instrument_library


class TestLibraryModel(uitest_utils.TestMixin, instrument_library.LibraryModelImpl):
    pass


class TracksModelTest(uitest_utils.UITest):
    async def setUp(self):
        await super().setUp()

    def __mkinstr(self, path):
        return instrument_db.InstrumentDescription(
            uri='wav:' + path,
            path=path,
            display_name=os.path.splitext(os.path.basename(path))[0],
            properties={})

    async def test_addInstrument(self):
        model = TestLibraryModel(**self.context)
        try:
            root_index = QtCore.QModelIndex()
            self.assertEqual(model.rowCount(root_index), 0)
            self.assertEqual(model.parent(root_index), QtCore.QModelIndex())

            model.addInstrument(self.__mkinstr('/test.wav'))
            self.assertEqual(model.rowCount(root_index), 1)

            folder1_index = model.index(0, parent=root_index)
            self.assertEqual(model.data(folder1_index, Qt.DisplayRole), '/')
            self.assertEqual(model.rowCount(folder1_index), 1)
            self.assertEqual(model.parent(folder1_index), root_index)

            instr1_index = model.index(0, parent=folder1_index)
            self.assertEqual(model.data(instr1_index, Qt.DisplayRole), 'test')
            self.assertEqual(model.rowCount(instr1_index), 0)
            self.assertEqual(model.parent(instr1_index), folder1_index)

        finally:
            model.close()

    async def test_addInstrument_long_path(self):
        model = TestLibraryModel(**self.context)
        try:
            model.addInstrument(self.__mkinstr('/some/path/test1.wav'))
            self.assertEqual(
                list(model.flattened()),
                [['/some/path'],
                 ['/some/path', 'test1']])

            model.addInstrument(self.__mkinstr('/some/path/test2.wav'))
            self.assertEqual(
                list(model.flattened()),
                [['/some/path'],
                 ['/some/path', 'test1'],
                 ['/some/path', 'test2']])

            model.addInstrument(self.__mkinstr('/some/path/more/test3.wav'))
            self.assertEqual(
                list(model.flattened()),
                [['/some/path'],
                 ['/some/path', 'more'],
                 ['/some/path', 'more', 'test3'],
                 ['/some/path', 'test1'],
                 ['/some/path', 'test2']])

            model.addInstrument(self.__mkinstr('/some/path2/test4.wav'))
            self.assertEqual(
                list(model.flattened()),
                [['/some'],
                 ['/some', 'path'],
                 ['/some', 'path', 'more'],
                 ['/some', 'path', 'more', 'test3'],
                 ['/some', 'path', 'test1'],
                 ['/some', 'path', 'test2'],
                 ['/some', 'path2'],
                 ['/some', 'path2', 'test4']])

        finally:
            model.close()



if __name__ == '__main__':
    unittest.main()
