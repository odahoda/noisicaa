#!/usr/bin/python3

import functools
import logging
import itertools

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.music import model
from .render_sheet_dialog import RenderSheetDialog
from .svg_symbol import SymbolItem
from .tool_dock import Tool
from .misc import QGraphicsGroup
from . import ui_base
from . import base_track_item
from . import score_track_item
from . import beat_track_item
from . import sheet_property_track_item
from . import control_track_item
from . import layout

logger = logging.getLogger(__name__)


class SheetScene(QtWidgets.QGraphicsScene):
    mouseHovers = QtCore.pyqtSignal(bool)

    def event(self, event):
        if event.type() == QtCore.QEvent.Enter:
            self.mouseHovers.emit(True)
        elif event.type() == QtCore.QEvent.Leave:
            self.mouseHovers.emit(False)
        return super().event(event)


class SheetViewImpl(QtWidgets.QGraphicsView):
    currentToolChanged = QtCore.pyqtSignal(Tool)

    track_cls_map = {
        'ScoreTrack': score_track_item.ScoreTrackItem,
        'BeatTrack': beat_track_item.BeatTrackItem,
        'SheetPropertyTrack': sheet_property_track_item.SheetPropertyTrackItem,
        'ControlTrack': control_track_item.ControlTrackItem,
    }

    def __init__(self, sheet, **kwargs):
        super().__init__(**kwargs)
        self._sheet = sheet

        self._pending_callbacks = None
        self._project_mutations_begin_listener = (
            self.project_client.listeners.add(
                'project_mutations_begin', self.onProjectMutationsBegin))
        self._project_mutations_end_listener = (
            self.project_client.listeners.add(
                'project_mutations_end', self.onProjectMutationsEnd))

        self._selection_set = set()

        self._track_items = {}
        self._group_listeners = {}
        self.addTrack(self._sheet.master_group)

        self._property_track_item = self.createTrackItem(
            self._sheet.property_track)

        self._layouts = []

        self._scene = SheetScene()
        self._scene.mouseHovers.connect(self.onMouseHovers)
        self.setScene(self._scene)

        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        #self.setDragMode(QGraphicsView.ScrollHandDrag)

        self.layers = {}
        for layer_id in range(base_track_item.Layer.NUM_LAYERS):
            layer = QGraphicsGroup()
            layer.setPos(0, 0)
            self.layers[layer_id] = layer
            self._scene.addItem(layer)

        self._current_tool = Tool.NOTE_QUARTER
        self._previous_tool = -1
        self._cursor = QGraphicsGroup(self.layers[base_track_item.Layer.MOUSE])

        self.updateSheet()

        self._time_mapper = music.TimeMapper(self._sheet)

        self._player_id = None
        self._player_stream_address = None
        self._player_node_id = None
        self._player_status_listener = None

        self.player_audioproc_address = None

        self._project_mutations_begin_listener = None
        self._project_mutations_end_listener = None

    async def setup(self):
        self._player_id, self._player_stream_address = await self.project_client.create_player(self._sheet.id)
        self._player_status_listener = self.project_client.add_player_status_listener(
            self._player_id, self.onPlayerStatus)

        self.player_audioproc_address = await self.project_client.get_player_audioproc_address(self._player_id)

        self._player_node_id = await self.audioproc_client.add_node(
            'ipc',
            address=self._player_stream_address,
            event_queue_name='sheet:%s' % self._sheet.id)
        await self.audioproc_client.connect_ports(
            self._player_node_id, 'out', 'sink', 'in')

    async def cleanup(self):
        if self._project_mutations_begin_listener is not None:
            self._project_mutations_begin_listener.remove()
            self._project_mutations_begin_listener = None

        if self._project_mutations_end_listener is not None:
            self._project_mutations_end_listener.remove()
            self._project_mutations_end_listener = None

        while len(self._track_items) > 0:
            self.removeTrack(next(self._track_items.values()))

        if self._player_node_id is not None:
            await self.audioproc_client.disconnect_ports(
                self._player_node_id, 'out', 'sink', 'in')
            await self.audioproc_client.remove_node(
                self._player_node_id)
            self._player_node_id = None
            self._player_stream_address = None

        if self._player_status_listener is not None:
            self._player_status_listener.remove()
            self._player_status_listener = None

        if self._player_id is not None:
            await self.project_client.delete_player(self._player_id)
            self._player_id = None

    @property
    def trackItems(self):
        return [
            self._track_items[track.id]
            for track in self._sheet.master_group.walk_tracks()]

    def clearSelection(self):
        for obj in self._selection_set:
            obj.setSelected(False)
        self._selection_set.clear()

    def addToSelection(self, obj):
        if obj in self._selection_set:
            raise RuntimeError("Item already selected.")

        if isinstance(obj, base_track_item.MeasureItemImpl):
            self._selection_set.add(obj)
            obj.setSelected(True)

        else:
            raise ValueError(type(obj))

    def removeFromSelection(self, obj, update_object=False):
        if obj not in self._selection_set:
            raise RuntimeError("Item not selected.")

        self._selection_set.remove(obj)
        if update_object:
            obj.setSelected(False)

    def setInfoMessage(self, msg):
        self.window.setInfoMessage(msg)

    def createTrackItem(self, track):
        track_item_cls = self.track_cls_map[type(track).__name__]
        return track_item_cls(
            **self.context, sheet_view=self, track=track)

    def addTrack(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            self.addSingleTrack(t)

    def addSingleTrack(self, track):
        if isinstance(track, model.TrackGroup):
            listener = track.listeners.add(
                'tracks',
                functools.partial(self.onTracksChanged, track))
            self._group_listeners[track.id] = listener
        else:
            track_item = self.createTrackItem(track)
            self._track_items[track.id] = track_item

    def removeTrack(self, track):
        for t in track.walk_tracks(groups=True, tracks=True):
            self.removeSingleTrack(t)

    def removeSingleTrack(self, track):
        if isinstance(track, model.TrackGroup):
            listener = self._group_listeners[track.id]
            listener.remove()
            del self._group_listeners[track.id]
        else:
            track_item = self._track_items[track.id]
            track_item.close()
            del self._track_items[track.id]

    @property
    def sheet(self):
        return self._sheet

    def currentTool(self):
        return self._current_tool

    def setCurrentTool(self, tool_id):
        if tool_id == self._current_tool:
            return

        tool = Tool(tool_id)
        assert tool_id >= 0

        self._previous_tool = self._current_tool
        self._current_tool = tool

        for child in self._cursor.childItems():
            child.setParentItem(None)
            if child.scene() is not None:
                self._scene.removeItem(child)

        if tool_id.is_note:
            cursor = QGraphicsGroup(self._cursor)

            if tool_id <= Tool.NOTE_HALF:
                body = SymbolItem('note-head-void', cursor)
            else:
                body = SymbolItem('note-head-black', cursor)

            if tool_id >= Tool.NOTE_HALF:
                arm = QtWidgets.QGraphicsRectItem(cursor)
                arm.setRect(8, -63, 3, 60)
                arm.setBrush(Qt.black)
                arm.setPen(QtGui.QPen(Qt.NoPen))

            if tool_id >= Tool.NOTE_8TH:
                for n in range(tool_id - Tool.NOTE_QUARTER):
                    flag = SymbolItem('note-flag-down', cursor)
                    flag.setPos(11, -63 + 12 * n)

            cursor.setScale(0.8)

        elif tool_id.is_rest:
            sym = {
                Tool.REST_WHOLE: 'rest-whole',
                Tool.REST_HALF: 'rest-half',
                Tool.REST_QUARTER: 'rest-quarter',
                Tool.REST_8TH: 'rest-8th',
                Tool.REST_16TH: 'rest-16th',
                Tool.REST_32TH: 'rest-32th',
            }[tool_id]
            cursor = SymbolItem(sym, self._cursor)
            cursor.setScale(0.8)

        elif tool_id.is_accidental:
            sym = {
                Tool.ACCIDENTAL_NATURAL: 'accidental-natural',
                Tool.ACCIDENTAL_SHARP: 'accidental-sharp',
                Tool.ACCIDENTAL_FLAT: 'accidental-flat',
                Tool.ACCIDENTAL_DOUBLE_SHARP: 'accidental-double-sharp',
                Tool.ACCIDENTAL_DOUBLE_FLAT: 'accidental-double-flat',
            }[tool_id]
            cursor = SymbolItem(sym, self._cursor)
            cursor.setScale(0.8)

        elif tool_id.is_duration:
            if tool_id == Tool.DURATION_DOT:
                body = SymbolItem('note-head-black', self._cursor)
                arm = QtWidgets.QGraphicsRectItem(self._cursor)
                arm.setRect(8, -63, 3, 60)
                arm.setBrush(Qt.black)
                arm.setPen(QtGui.QPen(Qt.NoPen))
                dot = QtWidgets.QGraphicsEllipseItem(self._cursor)
                dot.setRect(12, -4, 9, 9)
                dot.setBrush(Qt.black)
                dot.setPen(QtGui.QPen(Qt.NoPen))

            else:
                sym = {
                    Tool.DURATION_TRIPLET: 'duration-triplet',
                    Tool.DURATION_QUINTUPLET: 'duration-quintuplet',
                }[tool_id]
                SymbolItem(sym, self._cursor)

        else:  # pragma: no cover
            a = QtWidgets.QGraphicsEllipseItem(self._cursor)
            a.setRect(-5, -5, 11, 11)
            a.setPen(QtGui.QPen(Qt.white))
            a.setBrush(QtGui.QColor(100, 100, 100))
            a = QtWidgets.QGraphicsSimpleTextItem(self._cursor)
            a.setText(str(tool_id))
            a.setPos(10, 10)

        self.currentToolChanged.emit(self._current_tool)

    def onProjectMutationsBegin(self):
        self._pending_callbacks = {}

    def onProjectMutationsEnd(self):
        callbacks = list(self._pending_callbacks.values())
        self._pending_callbacks = None

        for callback in callbacks:
            callback()

    def scheduleCallback(self, cb_id, callback):
        if self._pending_callbacks is not None:
            if cb_id not in self._pending_callbacks:
                self._pending_callbacks[cb_id] = callback

        else:
            callback()

    def updateView(self):
        self.updateSheet()

    def clearLayer(self, layer):
        for item in layer.childItems():
            if item.scene() is not None:
                self._scene.removeItem(item)
            item.setParentItem(None)

    def updateSheet(self):
        for layer_id in (
                base_track_item.Layer.BG, base_track_item.Layer.MAIN,
                base_track_item.Layer.DEBUG, base_track_item.Layer.EVENTS):
            self.clearLayer(self.layers[layer_id])

        text = QtWidgets.QGraphicsSimpleTextItem(self.layers[base_track_item.Layer.MAIN])
        text.setText(
            "%s/%s" % (self.project_connection.name, self._sheet.name))
        text.setPos(0, 0)

        track_items = [self._property_track_item] + self.trackItems
        visible_track_items = [
            track_item for track_item in track_items if track_item.track.visible]

        sheet_layout = layout.SheetLayout()
        for track_item in visible_track_items:
            sheet_layout.add_track_layout(track_item.getLayout())
        sheet_layout.compute()

        y = 30
        for track, track_layout in zip(visible_track_items, sheet_layout.track_layouts):
            track.renderTrack(y, track_layout)

            y += track_layout.height + 20

        self.setSceneRect(-10, -10, sheet_layout.width + 20, y + 20)

        if self.app.showEditAreas:  # pragma: no cover
            bbox = QtWidgets.QGraphicsRectItem(self.layers[base_track_item.Layer.DEBUG])
            bbox.setRect(0, 0, sheet_layout.width, y)
            bbox.setPen(QtGui.QColor(200, 200, 200))
            bbox.setBrush(QtGui.QBrush(Qt.NoBrush))

        self.setSceneRect(-10, -10, sheet_layout.width + 20, y + 20)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        scenePos = self.mapToScene(event.pos())
        self._cursor.setPos(scenePos)

    def onMouseHovers(self, hovers):
        if hovers:
            self.setCursor(Qt.BlankCursor)
            self._cursor.show()
        else:
            self.unsetCursor()
            self._cursor.hide()

        if hovers:
            self.setFocus()

    def onTracksChanged(self, group, action, *args):
        if action == 'insert':
            idx, track = args
            self.addTrack(track)
            self.updateSheet()

        elif action == 'delete':
            idx, track = args
            self.removeTrack(track)
            self.updateSheet()

        else:  # pragma: no cover
            raise ValueError("Unknown action %r" % action)

    def onAddTrack(self, track_type):
        self.send_command_async(
            self._sheet.id, 'AddTrack', track_type=track_type)

    def onPlayerStart(self):
        if self._player_id is None:
            logger.warning("Player start action without active player.")
            return

        self.call_async(
            self.project_client.player_start(self._player_id))

    def onPlayerPause(self):
        if self._player_id is None:
            logger.warning("Player pause action without active player.")
            return

        self.call_async(
            self.project_client.player_pause(self._player_id))

    def onPlayerStop(self):
        if self._player_id is None:
            logger.warning("Player stop action without active player.")
            return

        self.call_async(
            self.project_client.player_stop(self._player_id))

    def onPlayerStatus(self, playback_pos=None, **kwargs):
        if playback_pos is not None:
            sample_pos, num_samples = playback_pos

            start_tick = self._time_mapper.sample2tick(
                sample_pos % self._time_mapper.total_duration_samples)
            start_measure_idx, start_measure_tick = (
                self._time_mapper.measure_pos(start_tick))

            end_tick = self._time_mapper.sample2tick(
                (sample_pos + num_samples)
                % self._time_mapper.total_duration_samples)
            end_measure_idx, end_measure_tick = (
                self._time_mapper.measure_pos(end_tick))

            for track in [self._property_track_item] + self.trackItems:
                track.setPlaybackPos(
                    sample_pos, num_samples,
                    start_measure_idx, start_measure_tick,
                    end_measure_idx, end_measure_tick)

    def onRender(self):
        dialog = RenderSheetDialog(self, self.app, self._sheet)
        dialog.exec_()


    def onCopy(self):
        if not self._selection_set:
            return

        self.call_async(self.onCopyAsync())

    async def onCopyAsync(self):
        data = []
        for obj in self._selection_set:
            data.append(await obj.getCopy())

        self.window.setClipboardContent(
            {'type': 'measures', 'data': data})

    def onPasteAsLink(self):
        if not self._selection_set:
            return

        clipboard = self.window.clipboardContent()
        if clipboard['type'] == 'measures':
            self.send_command_async(
                self._sheet.id, 'PasteMeasuresAsLink',
                src_ids=[copy['id'] for copy in clipboard['data']],
                target_ids=[
                    mref.id for mref in sorted(
                        (measure_item.measure_reference
                         for measure_item in self._selection_set),
                        key=lambda mref: mref.index)])

        else:
            raise ValueError(clipboard['type'])

    def scrollToPlaybackPosition(self, pos):
        # I would rather like to keep the pos in the left 1/3rd of the view.
        # But haven't figured out how to do that...
        self.ensureVisible(
            pos.x(), self.mapToScene(0, self.size().height() / 2).y(),
            1, 1,
            self.size().width() / 3, 0)

    def keyPressEvent(self, event):
        try:
            if event.isAutoRepeat():
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_Period:
                self.setCurrentTool(Tool.DURATION_DOT)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_F:
                self.setCurrentTool(Tool.ACCIDENTAL_FLAT)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_S:
                self.setCurrentTool(Tool.ACCIDENTAL_SHARP)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_N:
                self.setCurrentTool(Tool.ACCIDENTAL_NATURAL)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_R:
                self.setCurrentTool({
                    Tool.NOTE_WHOLE: Tool.REST_WHOLE,
                    Tool.NOTE_HALF: Tool.REST_HALF,
                    Tool.NOTE_QUARTER: Tool.REST_QUARTER,
                    Tool.NOTE_8TH: Tool.REST_8TH,
                    Tool.NOTE_16TH: Tool.REST_16TH,
                    Tool.NOTE_32TH: Tool.REST_32TH,
                    Tool.REST_WHOLE: Tool.NOTE_WHOLE,
                    Tool.REST_HALF: Tool.NOTE_HALF,
                    Tool.REST_QUARTER: Tool.NOTE_QUARTER,
                    Tool.REST_8TH: Tool.NOTE_8TH,
                    Tool.REST_16TH: Tool.NOTE_16TH,
                    Tool.REST_32TH: Tool.NOTE_32TH,
                }.get(self.currentTool(), Tool.REST_QUARTER))
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_1:
                self.setCurrentTool(Tool.NOTE_WHOLE if not self.currentTool().is_rest else Tool.REST_WHOLE)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_2:
                self.setCurrentTool(Tool.NOTE_HALF if not self.currentTool().is_rest else Tool.REST_HALF)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_3:
                self.setCurrentTool(Tool.NOTE_QUARTER if not self.currentTool().is_rest else Tool.REST_QUARTER)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_4:
                self.setCurrentTool(Tool.NOTE_8TH if not self.currentTool().is_rest else Tool.REST_8TH)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_5:
                self.setCurrentTool(Tool.NOTE_16TH if not self.currentTool().is_rest else Tool.REST_16TH)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_6:
                self.setCurrentTool(Tool.NOTE_32TH if not self.currentTool().is_rest else Tool.REST_32TH)

                event.accept()
                return

        finally:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        try:
            if event.isAutoRepeat():
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_Period:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_F:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_S:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

            if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_N:
                self.setCurrentTool(self._previous_tool)
                event.accept()
                return

        finally:
            super().keyReleaseEvent(event)


class SheetView(ui_base.ProjectMixin, SheetViewImpl):
    pass
