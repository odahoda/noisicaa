#!/usr/bin/python3

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


    async def test_start_empty(self):
        model = TestLibraryModel(**self.context)
        try:
            root_index = QtCore.QModelIndex()
            self.assertEqual(model.rowCount(root_index), 0)
            self.assertEqual(model.parent(root_index), QtCore.QModelIndex())

            model.addInstrument(
                instrument_db.InstrumentDescription(
                    uri='sf2:/tmp/test.sf2?bank=0&preset=0',
                    path='/test.sf2',
                    display_name='Piano',
                    properties={}))
            self.assertEqual(model.rowCount(root_index), 1)

            folder1_index = model.index(0, parent=root_index)
            self.assertEqual(model.data(folder1_index, Qt.DisplayRole), '/')
            self.assertEqual(model.rowCount(folder1_index), 1)
            self.assertEqual(model.parent(folder1_index), root_index)

            instr1_index = model.index(0, parent=folder1_index)
            self.assertEqual(model.data(instr1_index, Qt.DisplayRole), 'Piano')
            self.assertEqual(model.rowCount(instr1_index), 0)
            self.assertEqual(model.parent(instr1_index), folder1_index)


        finally:
            model.close()



if __name__ == '__main__':
    unittest.main()
