#/usr/bin/python3

import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

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
