#/usr/bin/python3

import unittest
from unittest import mock

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from noisicaa import music
from . import uitest_utils
from . import render_sheet_dialog


class RenderSheetDialogTest(uitest_utils.UITest):
    async def setUp(self):
        await super().setUp()
        self.project = music.BaseProject()
        self.sheet = self.project.sheets[0]

    def test_init(self):
        dialog = render_sheet_dialog.RenderSheetDialog(None, self.app, self.sheet)
        self.assertTrue(dialog.close())


if __name__ == '__main__':
    unittest.main()
