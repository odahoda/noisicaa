#!/usr/bin/python3

import itertools


class SheetLayout(object):
    def __init__(self):
        self.track_layouts = []
        self._width = None

    def add_track_layout(self, track_layout):
        self.track_layouts.append(track_layout)

    def compute(self, scale_x):
        self._width = 0
        for track_layout in self.track_layouts:
            track_layout.compute(scale_x)
            self._width = max(self._width, track_layout.width)

    @property
    def width(self):
        assert self._width is not None
        return self._width


class TrackLayout(object):
    def compute(self, scale_x):
        raise NotImplementedError

    @property
    def width(self):
        raise NotImplementedError

    @property
    def height(self):
        raise NotImplementedError
