#!/usr/bin/python3

from fractions import Fraction
import logging

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.music import model
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item
from . import layout

logger = logging.getLogger(__name__)


class SampleTrackLayout(layout.TrackLayout):
    def __init__(self, track):
        super().__init__()
        self._track = track
        self._widths = []

    def compute(self, scale_x):
        timepos = Fraction(0, 1)
        x = 0

        for mref in self._track.sheet.property_track.measure_list:
            measure = mref.measure

            end_timepos = timepos + measure.duration
            end_x = int(scale_x * end_timepos)
            width = end_x - x

            self._widths.append(width)

            timepos = end_timepos
            x = end_x

    @property
    def widths(self):
        return self._widths

    @property
    def width(self):
        return sum(self.widths)

    @property
    def height(self):
        return 120


class SampleTrackItemImpl(base_track_item.TrackItemImpl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def close(self):
        super().close()

    def getLayout(self):
        return SampleTrackLayout(self._track)

    def renderTrack(self, y, track_layout):
        layer = self._sheet_view.layers[base_track_item.Layer.MAIN]

        text = QtWidgets.QGraphicsSimpleTextItem(layer)
        text.setText("> %s" % self._track.name)
        text.setPos(0, y)

        r = QtWidgets.QGraphicsRectItem(layer)
        r.setRect(0, 0, track_layout.width, track_layout.height - 20)
        r.setPen(Qt.black)
        r.setBrush(QtGui.QBrush(Qt.NoBrush))
        r.setPos(0, y + 20)

    def setPlaybackPos(
            self, sample_pos, num_samples, start_measure_idx,
            start_measure_tick, end_measure_idx, end_measure_tick):
        pass


class SampleTrackItem(ui_base.ProjectMixin, SampleTrackItemImpl):
    pass
