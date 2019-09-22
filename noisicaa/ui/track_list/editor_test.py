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

from PyQt5 import QtGui

from noisidev import uitest
from noisicaa.ui import player_state
from . import editor


class TrackEditorItemTestMixin(uitest.ProjectMixin, uitest.UITestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = None

    async def setup_testcase(self):
        self.player_state = player_state.PlayerState(context=self.context)
        self.editor = editor.Editor(
            player_state=self.player_state,
            context=self.context)
        self.editor.resize(800, 400)
        self.setWidgetUnderTest(self.editor)

    async def cleanup_testcase(self):
        if self.editor is not None:
            self.editor.cleanup()

    def test_add_track(self):
        with self.project.apply_mutations('test'):
            self.project.create_node('builtin://pianoroll-track')

        self.renderWidget()
