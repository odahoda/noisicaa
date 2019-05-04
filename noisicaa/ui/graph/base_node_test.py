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

from PyQt5 import QtCore

from noisidev import uitest
from noisicaa import value_types
from . import base_node


class NoteTest(uitest.ProjectMixin, uitest.UITestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.node = None
        self.nitem = None

    async def setup_testcase(self):
        with self.project.apply_mutations():
            self.node = self.project.create_node(
                'ladspa://passthru.so/passthru',
                graph_pos=value_types.Pos2F(200, 100),
                graph_size=value_types.SizeF(140, 65))

        self.nitem = base_node.Node(node=self.node, context=self.context)

    async def cleanup_testcase(self):
        if self.nitem is not None:
            self.nitem.cleanup()

    def _scaledSize(self, zoom):
        return QtCore.QSize(
            int(zoom * self.nitem.sceneSize().width()),
            int(zoom * self.nitem.sceneSize().height()))

    async def test_attrs(self):
        self.assertEqual(self.nitem.id(), self.node.id)
        self.assertEqual(self.nitem.contentTopLeft(), QtCore.QPointF(200, 100))
        self.assertEqual(self.nitem.contentSize(), QtCore.QSizeF(140, 65))
        self.assertEqual(self.nitem.contentRect(), QtCore.QRectF(200, 100, 140, 65))
