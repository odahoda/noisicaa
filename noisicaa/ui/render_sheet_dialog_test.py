#/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import unittest

from noisicaa.music import project
from noisicaa.music import sheet
from . import uitest_utils
from . import render_sheet_dialog


# class RenderSheetDialogTest(uitest_utils.UITest):
#     async def setUp(self):
#         await super().setUp()
#         self.project = project.BaseProject()
#         self.project.sheets.append(sheet.Sheet(name='Sheet 1'))
#         self.sheet = self.project.sheets[0]

#     async def test_init(self):
#         dialog = render_sheet_dialog.RenderSheetDialog(None, self.app, self.sheet)
#         self.assertTrue(dialog.close())


if __name__ == '__main__':
    unittest.main()
