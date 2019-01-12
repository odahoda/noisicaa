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

# from noisidev import uitest
# from noisicaa import music
# from . import control_track_item
# from . import track_item_tests


# class ControlTrackEditorItemTest(track_item_tests.TrackEditorItemTestMixin, uitest.UITestCase):
#     async def setup_testcase(self):
#         await self.project_client.send_command(music.Command(
#             target=self.project.id,
#             add_track=music.AddTrack(
#                 track_type='control',
#                 parent_group_id=self.project.master_group.id)))

#         self.tool_box = control_track_item.ControlTrackToolBox(context=self.context)

#     def _createTrackItem(self, **kwargs):
#         return control_track_item.ControlTrackEditorItem(
#             track=self.project.master_group.tracks[0],
#             player_state=self.player_state,
#             editor=self.editor,
#             context=self.context,
#             **kwargs)
