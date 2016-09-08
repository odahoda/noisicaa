#!/usr/bin/python3

import unittest
from unittest import mock

from noisicaa import music
from . import layout


class TestTrackLayout(layout.TrackLayout):
    def __init__(self, points):
        super().__init__()
        self._points = points

    def list_points(self):
        yield from self._points


class LayoutTest(unittest.TestCase):
    def test_layout(self):
        sheet_layout = layout.SheetLayout()

        track_layout1 = TestTrackLayout([
            (10, 200),
            (20, 200),
        ])
        sheet_layout.add_track_layout(track_layout1)

        track_layout2 = TestTrackLayout([
            (10, 150),
            (20, 250),
        ])
        sheet_layout.add_track_layout(track_layout2)

        sheet_layout.compute()


if __name__ == '__main__':
    unittest.main()
