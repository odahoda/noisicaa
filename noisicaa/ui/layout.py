#!/usr/bin/python3

import itertools


class SheetLayout(object):
    def __init__(self):
        self.track_layouts = []
        self._width = None

    def add_track_layout(self, track_layout):
        self.track_layouts.append(track_layout)

    def compute(self):
        points = itertools.zip_longest(
            *(track_layout.list_points() for track_layout in self.track_layouts))
        widths = []
        current_pos = 0
        self._width = 0
        for column in points:
            current_point = None
            max_width = 0
            for point, width in (a for a in column if a is not None):
                if current_point is None:
                    current_point = point
                elif point != current_point:
                    raise AssertionError("All points must match up...")
                max_width = max(max_width, width)

            assert current_point is not None
            widths.append((current_point, max_width))
            self._width += max_width

        for track_layout in self.track_layouts:
            track_layout.set_widths(widths)

    @property
    def width(self):
        assert self._width is not None
        return self._width


class TrackLayout(object):
    def __init__(self):
        self._widths = None

    def list_points(self):
        raise NotImplementedError

    def set_widths(self, widths):
        assert self._widths is None
        self._widths = widths

    @property
    def height(self):
        raise NotImplementedError
