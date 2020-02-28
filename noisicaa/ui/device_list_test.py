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

from PyQt5.QtCore import Qt
from PyQt5 import QtCore

from noisidev import uitest
from noisicaa import audioproc
from . import device_list


class DeviceListTest(uitest.UITestCase):
    def assertIndexEqual(self, i1, i2):
        def cmp_index(i1, i2):
            if not i1.isValid() and not i2.isValid():
                return True
            return (
                i1.row() == i2.row()
                and i1.column() == i2.column()
                and cmp_index(i1.parent(), i2.parent()))

        def format_index(i):
            if not i.isValid():
                return ''
            s = format_index(i.parent())
            if s:
                s += '>'
            s += '[%d,%d]' % (i.row(), i.column())
            return s

        self.assertTrue(cmp_index(i1, i2), '%s != %s' % (format_index(i1), format_index(i2)))

    def fill_model(self, model):
        for i in range(5):
            model.addDevice(audioproc.DeviceDescription(
                uri='alsa://%d'  % (i + 10),
                type=audioproc.DeviceDescription.MIDI_CONTROLLER,
                display_name='holla %d' % (i + 1),
                ports=[
                    audioproc.DevicePortDescription(
                        uri='alsa://%d/0' % (i + 10),
                        type=audioproc.DevicePortDescription.MIDI,
                        display_name='port1',
                        readable=True,
                        writable=True),
                ]))

    async def test_addDevice_at_bottom(self):
        model = device_list.DeviceList()
        self.fill_model(model)

        root_index = QtCore.QModelIndex()
        self.assertEqual(model.rowCount(root_index), 5)
        self.assertEqual(model.parent(root_index), QtCore.QModelIndex())

        model.addDevice(audioproc.DeviceDescription(
            uri='alsa://20',
            type=audioproc.DeviceDescription.MIDI_CONTROLLER,
            display_name='knut',
            ports=[
                audioproc.DevicePortDescription(
                    uri='alsa://20/0',
                    type=audioproc.DevicePortDescription.MIDI,
                    display_name='port1',
                    readable=True,
                    writable=True),
            ]))
        self.assertEqual(model.rowCount(root_index), 6)

        dev1_index = model.index(5, parent=root_index)
        self.assertEqual(model.data(dev1_index, Qt.UserRole), 'alsa://20')
        self.assertEqual(model.data(dev1_index, Qt.DisplayRole), 'knut')
        self.assertEqual(model.rowCount(dev1_index), 1)
        self.assertIndexEqual(model.parent(dev1_index), root_index)

        dev1p1_index = model.index(0, parent=dev1_index)
        self.assertEqual(model.data(dev1p1_index, Qt.UserRole), 'alsa://20/0')
        self.assertEqual(model.data(dev1p1_index, Qt.DisplayRole), 'port1')
        self.assertEqual(model.rowCount(dev1p1_index), 0)
        self.assertIndexEqual(model.parent(dev1p1_index), dev1_index)

    async def test_addDevice_at_top(self):
        model = device_list.DeviceList()
        self.fill_model(model)

        root_index = QtCore.QModelIndex()
        self.assertEqual(model.rowCount(root_index), 5)
        self.assertEqual(model.parent(root_index), QtCore.QModelIndex())

        model.addDevice(audioproc.DeviceDescription(
            uri='alsa://20',
            type=audioproc.DeviceDescription.MIDI_CONTROLLER,
            display_name='anna',
            ports=[
                audioproc.DevicePortDescription(
                    uri='alsa://20/0',
                    type=audioproc.DevicePortDescription.MIDI,
                    display_name='port1',
                    readable=True,
                    writable=True),
            ]))
        self.assertEqual(model.rowCount(root_index), 6)

        dev1_index = model.index(0, parent=root_index)
        self.assertEqual(model.data(dev1_index, Qt.UserRole), 'alsa://20')
        self.assertEqual(model.data(dev1_index, Qt.DisplayRole), 'anna')
        self.assertEqual(model.rowCount(dev1_index), 1)
        self.assertIndexEqual(model.parent(dev1_index), root_index)

        dev1p1_index = model.index(0, parent=dev1_index)
        self.assertEqual(model.data(dev1p1_index, Qt.UserRole), 'alsa://20/0')
        self.assertEqual(model.data(dev1p1_index, Qt.DisplayRole), 'port1')
        self.assertEqual(model.rowCount(dev1p1_index), 0)
        self.assertIndexEqual(model.parent(dev1p1_index), dev1_index)

    async def test_addDevice_middle(self):
        model = device_list.DeviceList()
        self.fill_model(model)

        root_index = QtCore.QModelIndex()
        self.assertEqual(model.rowCount(root_index), 5)
        self.assertEqual(model.parent(root_index), QtCore.QModelIndex())

        model.addDevice(audioproc.DeviceDescription(
            uri='alsa://20',
            type=audioproc.DeviceDescription.MIDI_CONTROLLER,
            display_name='holla 2b',
            ports=[
                audioproc.DevicePortDescription(
                    uri='alsa://20/0',
                    type=audioproc.DevicePortDescription.MIDI,
                    display_name='port1',
                    readable=True,
                    writable=True),
            ]))
        self.assertEqual(model.rowCount(root_index), 6)

        dev1_index = model.index(2, parent=root_index)
        self.assertEqual(model.data(dev1_index, Qt.UserRole), 'alsa://20')
        self.assertEqual(model.data(dev1_index, Qt.DisplayRole), 'holla 2b')
        self.assertEqual(model.rowCount(dev1_index), 1)
        self.assertIndexEqual(model.parent(dev1_index), root_index)

        dev1p1_index = model.index(0, parent=dev1_index)
        self.assertEqual(model.data(dev1p1_index, Qt.UserRole), 'alsa://20/0')
        self.assertEqual(model.data(dev1p1_index, Qt.DisplayRole), 'port1')
        self.assertEqual(model.rowCount(dev1p1_index), 0)
        self.assertIndexEqual(model.parent(dev1p1_index), dev1_index)
