#!/usr/bin/python3

import logging
import enum

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from .misc import QGraphicsGroup
from . import layout

logger = logging.getLogger(__name__)


class Layer(enum.IntEnum):
    BG = 0
    MAIN = 1
    DEBUG = 2
    EDIT = 3
    MOUSE = 4
    EVENTS = 5

    NUM_LAYERS = 6



class TrackItemImpl(object):
    def __init__(self, sheet_view, track, **kwargs):
        super().__init__(**kwargs)
        self._sheet_view = sheet_view
        self._track = track

        self._layout = None

        self._listeners = [
            self._track.listeners.add('name', self.onNameChanged),
            self._track.listeners.add('muted', self.onMutedChanged),
            self._track.listeners.add('volume', self.onVolumeChanged),
            self._track.listeners.add('visible', self.onVisibleChanged),
        ]

    def close(self):
        for listener in self._listeners:
            listener.remove()

    @property
    def track(self):
        return self._track

    def onNameChanged(self, old_name, new_name):
        # TODO: only update the first measure.
        self._sheet_view.updateSheet()

    def onMutedChanged(self, old_value, new_value):
        pass # TODO

    def onVolumeChanged(self, old_value, new_value):
        pass # TODO

    def onVisibleChanged(self, old_value, new_value):
        self._sheet_view.updateSheet()

    def getLayout(self):
        raise NotImplementedError

    def renderTrack(self, y, track_layout):
        self._layout = track_layout

    def buildContextMenu(self, menu):
        track_properties_action = QtWidgets.QAction(
            "Edit track properties...", menu,
            statusTip="Edit the properties of this track.",
            triggered=self.onTrackProperties)
        menu.addAction(track_properties_action)

        remove_track_action = QtWidgets.QAction(
            "Remove track", menu,
            statusTip="Remove this track.",
            triggered=self.onRemoveTrack)
        menu.addAction(remove_track_action)

    def onRemoveTrack(self):
        self.send_command_async(
            self._track.parent.id, 'RemoveTrack',
            track=self._track.index)

    def onTrackProperties(self):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("Track Properties")

        name = QtWidgets.QLineEdit(dialog)
        name.setText(self._track.name)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Name", name)

        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(dialog.close)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addLayout(buttons)
        dialog.setLayout(layout)

        ret = dialog.exec_()

        self.send_command_async(
            self._track.id, 'UpdateTrackProperties',
            name=name.text())


class MeasureLayout(object):
    def __init__(self):
        self.size = QtCore.QSize()
        self.baseline = 0

    @property
    def is_valid(self):
        return self.width > 0 and self.height > 0

    @property
    def width(self):
        return self.size.width()

    @width.setter
    def width(self, value):
        self.size.setWidth(value)

    @property
    def height(self):
        return self.size.height()

    @height.setter
    def height(self, value):
        self.size.setHeight(value)

    @property
    def extend_above(self):
        return self.baseline

    @property
    def extend_below(self):
        return self.height - self.baseline

    def __eq__(self, other):
        assert isinstance(other, MeasureLayout)
        return (self.size == other.size) and (self.baseline == other.baseline)


class MeasureItemImpl(QtWidgets.QGraphicsObject):
    def __init__(self, sheet_view, track_item, measure_reference, **kwargs):
        super().__init__(**kwargs)
        self._sheet_view = sheet_view
        self._track_item = track_item
        self._measure_reference = measure_reference
        if self._measure_reference is not None:
            self._measure = measure_reference.measure
            self._measure_listener = self._measure_reference.listeners.add(
                'measure_id', self.measureChanged)
        else:
            self._measure = None
            self._measure_listener = None

        self._layout = None

        self._layers = {}
        self._layers[Layer.BG] = QGraphicsGroup()

        self._background = QtWidgets.QGraphicsRectItem(self._layers[Layer.BG])
        self._background.setPen(QtGui.QPen(Qt.NoPen))
        self._background.setBrush(QtGui.QColor(240, 240, 255))
        self._background.setVisible(False)

        self._selected = False

        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable)

    @property
    def measure(self):
        return self._measure

    @property
    def measure_reference(self):
        return self._measure_reference

    @property
    def track_item(self):
        return self._track_item

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self._layout.width, self._layout.height)

    def paint(self, painter, option, widget=None):
        pass

    def close(self):
        if self._measure_listener is not None:
            self._measure_listener.remove()

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)

        self.setFocus()

    def measureChanged(self, old_value, new_value):
        self._measure = self._measure_reference.measure
        self.recomputeLayout()

    def recomputeLayout(self):
        self._sheet_view.scheduleCallback(
            '%s:recomputeLayout' % id(self),
            self._recomputeLayoutInternal)

    def _recomputeLayoutInternal(self):
        layout = self.getLayout()
        if layout != self._layout:
            self._sheet_view.updateSheet()
        else:
            self.updateMeasure()

    def getLayout(self):
        raise NotImplementedError

    def setLayout(self, layout):
        self._layout = layout

    def updateMeasure(self):
        self._sheet_view.scheduleCallback(
            '%s:updateMeasure' % id(self),
            self._updateMeasureInternal)

    def _updateMeasureInternal(self):
        raise NotImplementedError

    @property
    def layers(self):
        return sorted(self._layers.keys())

    def getLayer(self, layer_id):
        return self._layers.get(layer_id, None)

    def width(self):
        return self._layout.width

    def buildContextMenu(self, menu):
        insert_measure_action = QtWidgets.QAction(
            "Insert measure", menu,
            statusTip="Insert an empty measure at this point.",
            triggered=self.onInsertMeasure)
        menu.addAction(insert_measure_action)

        remove_measure_action = QtWidgets.QAction(
            "Remove measure", menu,
            statusTip="Remove this measure.",
            triggered=self.onRemoveMeasure)
        menu.addAction(remove_measure_action)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        self._track_item.buildContextMenu(menu)
        self.buildContextMenu(menu)

        menu.exec_(event.screenPos())
        event.accept()

    def onInsertMeasure(self):
        self.send_command_async(
            self._sheet_view.sheet.id, 'InsertMeasure',
            tracks=[self._measure.track.index],
            pos=self._measure_reference.index)

    def onRemoveMeasure(self):
        self.send_command_async(
            self._sheet_view.sheet.id, 'RemoveMeasure',
            tracks=[self._measure.track.index],
            pos=self._measure_reference.index)

    def mousePressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if self.selected():
                self._sheet_view.removeFromSelection(self)
            else:
                self._sheet_view.clearSelection()
                self._sheet_view.addToSelection(self)
            event.accept()
            return

        return super().mousePressEvent(event)

    def clearPlaybackPos(self):
        pass

    def setPlaybackPos(
            self, sample_pos, num_samples, start_tick, end_tick, first):
        pass

    def setSelected(self, selected):
        if selected != self._selected:
            self._selected = selected
            self._background.setVisible(self._selected)
            self.updateMeasure()

    def selected(self):
        return self._selected

    async def getCopy(self):
        return {'class': type(self._measure).__name__,
                'id': self._measure.id,
                'data': await self.project_client.serialize(self._measure.id) }


class MeasuredTrackLayout(layout.TrackLayout):
    def __init__(self):
        super().__init__()

        self.measure_layouts = []
        self._height_above = 0
        self._height_below = 0

    def add_measure_layout(self, measure_layout):
        self.measure_layouts.append(measure_layout)
        self._height_above = max(self._height_above, measure_layout.extend_above)
        self._height_below = max(self._height_below, measure_layout.extend_below)

    def list_points(self):
        for pos, measure_layout in enumerate(self.measure_layouts):
            yield (pos, measure_layout.width)

    def set_widths(self, widths):
        super().set_widths(widths)

        for measure_layout, (pos, width) in zip(self.measure_layouts, widths):
            measure_layout.width = width

    @property
    def height(self):
        return self._height_above + self._height_below


class MeasuredTrackItemImpl(TrackItemImpl):
    measure_item_cls = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._prev_playback_measures = set()

        self._measures = []
        for mref in self._track.measure_list:
            measure_item = self.measure_item_cls(  # pylint: disable=not-callable
                **self.context, sheet_view=self._sheet_view,
                track_item=self, measure_reference=mref)
            self._measures.append(measure_item)

        self._ghost_measure_item = self.measure_item_cls(  # pylint: disable=not-callable
            **self.context, sheet_view=self._sheet_view,
            track_item=self, measure_reference=None)

        self._listeners.append(self._track.listeners.add(
            'measure_list', self.onMeasureListChanged))

    def close(self):
        super.close()

        while len(self._measures) > 0:
            measure = self._measures.pop(0)
            if measure.selected():
                self._sheet_view.removeFromSelection(
                    measure, update_object=False)
            measure.close()
        self._ghost_measure_item.close()
        self._ghost_measure_item = None

    @property
    def measures(self):
        return self._measures + [self._ghost_measure_item]

    def removeMeasure(self, idx):
        measure = self._measures[idx]
        if measure.selected():
            self._sheet_view.removeFromSelection(measure, update_object=False)
        measure.close()
        del self._measures[idx]

    def onMeasureListChanged(self, action, *args):
        if action == 'insert':
            idx, measure_reference = args
            measure_item = self.measure_item_cls(  # pylint: disable=not-callable
                **self.context, sheet_view=self._sheet_view,
                track_item=self, measure_reference=measure_reference)
            self._measures.insert(idx, measure_item)
            self._sheet_view.updateSheet()

        elif action == 'delete':
            idx, measure_reference = args
            self.removeMeasure(idx)
            self._sheet_view.updateSheet()

        else:
            raise ValueError("Unknown action %r" % action)

    def getLayout(self):
        track_layout = MeasuredTrackLayout()
        for measure_item in self.measures:
            track_layout.add_measure_layout(measure_item.getLayout())
        return track_layout

    def renderTrack(self, y, track_layout):
        super().renderTrack(y, track_layout)

        x = 0
        for measure, measure_layout in zip(self.measures, self._layout.measure_layouts):
            measure.setLayout(measure_layout)
            measure.updateMeasure()
            for mlayer_id in measure.layers:
                slayer = self._sheet_view.layers[mlayer_id]
                mlayer = measure.getLayer(mlayer_id)
                assert mlayer is not None
                mlayer.setParentItem(slayer)
                mlayer.setPos(x, y)
            measure.setParentItem(self._sheet_view.layers[Layer.EVENTS])
            measure.setPos(x, y)

            x += measure_layout.width

    def setPlaybackPos(
            self, sample_pos, num_samples, start_measure_idx,
            start_measure_tick, end_measure_idx, end_measure_tick):
        playback_measures = set()

        measure_idx = start_measure_idx
        first = True
        while True:
            measure_item = self.measures[measure_idx]
            if measure_idx == start_measure_idx:
                start_tick = start_measure_tick
            else:
                start_tick = 0
            if measure_idx == end_measure_idx:
                end_tick = end_measure_tick
            else:
                end_tick = measure_item.measure.duration.ticks
            measure_item.setPlaybackPos(
                sample_pos, num_samples, start_tick, end_tick, first)
            playback_measures.add(measure_idx)

            if measure_idx == end_measure_idx:
                break

            measure_idx = (measure_idx + 1) % len(self._track.measure_list)
            first = False

        for measure_idx in self._prev_playback_measures - playback_measures:
            self.measures[measure_idx].clearPlaybackPos()
        self._prev_playback_measures = playback_measures

    def onPasteMeasuresAsLink(self, data):
        print(data)
