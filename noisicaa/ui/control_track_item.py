#!/usr/bin/python3

import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.music import model
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item
from . import layout

logger = logging.getLogger(__name__)


class ControlTrackLayout(layout.TrackLayout):
    def __init__(self, track):
        super().__init__()
        self._track = track

    def list_points(self):
        num_measures = max(
            len(track.measure_list) for track in self._track.sheet.all_tracks
            if isinstance(track, model.MeasuredTrack))
        for pos in range(num_measures):
            yield (pos, 100)

    def set_widths(self, widths):
        super().set_widths(widths)

    @property
    def widths(self):
        return [width for _, width in self._widths]

    @property
    def width(self):
        return sum(self.widths)

    @property
    def height(self):
        return 40


class ControlTrackItemImpl(base_track_item.TrackItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def getLayout(self):
        return ControlTrackLayout(self._track)

    def renderTrack(self, y, track_layout):
        layer = self._sheet_view.layers[base_track_item.Layer.MAIN]

        r = QtWidgets.QGraphicsRectItem(layer)
        r.setRect(0, 0, track_layout.width, track_layout.height)
        r.setPen(Qt.black)
        r.setBrush(Qt.red)
        r.setPos(0, y)

class ControlTrackItem(ui_base.ProjectMixin, ControlTrackItemImpl):
    pass
