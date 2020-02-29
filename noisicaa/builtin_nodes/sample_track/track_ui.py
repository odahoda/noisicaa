#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import asyncio
import concurrent.futures
import fractions
import functools
import logging
import math
import mmap
import os.path
import random
import time as time_lib
import traceback
from typing import Any, BinaryIO, Dict, List, Tuple

import numpy
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa.ui.track_list import base_track_editor
from noisicaa.ui.track_list import time_view_mixin
from noisicaa.ui.track_list import tools
from . import model

logger = logging.getLogger(__name__)


class EditSamplesTool(tools.ToolBase):
    track = None  # type: SampleTrackEditor

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            type=tools.ToolType.EDIT_SAMPLES,
            group=tools.ToolGroup.EDIT,
            **kwargs)

        self.__moving_sample = None  # type: SampleItem
        self.__moving_sample_original_pos = None  # type: QtCore.QPoint
        self.__moving_sample_offset = None  # type: QtCore.QPoint

    def iconName(self) -> str:
        return 'edit-samples'

    def onAddSampleSync(self, time: audioproc.MusicalTime) -> None:
        filters = [
            "All Files (*)",
            "Audio Files (*.wav *.mp3)",
            "Wav (*.wav)",
            "MP3 (*.mp3)",
        ]
        path, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            parent=self.track,
            caption="Add Sample to track \"%s\"" % self.track.track.name,
            directory=self.get_session_value(
                'sample-track:add-sample-dialog:directory', None),
            filter=';;'.join(filters),
            initialFilter=self.get_session_value(
                'sample-track:add-sample-dialog:selected-filter', filters[1]),
        )
        if not path:
            return

        self.set_session_value('sample-track:add-sample-dialog:directory', os.path.dirname(path))
        self.set_session_value('sample-track:add-sample-dialog:selected-filter', selected_filter)

        self.call_async(self.onAddSample(path, time))

    async def onAddSample(self, path: str, time: audioproc.MusicalTime) -> None:
        progress_dialog = QtWidgets.QProgressDialog(self.track)
        progress_dialog.setModal(True)
        progress_dialog.setLabelText("Importing sample...")

        class Cancelled(Exception):
            pass

        def progress_cb(progress: float) -> None:
            if progress_dialog.wasCanceled():
                raise Cancelled()
            progress_dialog.show()
            progress_dialog.setValue(int(100 * progress))

        try:
            try:
                loaded_sample = await self.track.track.load_sample(
                    path, self.event_loop, progress_cb)
            finally:
                progress_dialog.close()

        except model.SampleLoadError as exc:
            dialog = QtWidgets.QMessageBox(self.track)
            dialog.setObjectName('sample-load-error')
            dialog.setWindowTitle("noisicaä - Error")
            dialog.setIcon(QtWidgets.QMessageBox.Critical)
            dialog.setText("Failed to import sample from \"%s\"." % path)
            dialog.setInformativeText(str(exc))
            buttons = QtWidgets.QMessageBox.StandardButtons()
            buttons |= QtWidgets.QMessageBox.Close
            dialog.setStandardButtons(buttons)
            # TODO: Even with the size grip enabled, the dialog window is not resizable.
            # Might be a bug in Qt: https://bugreports.qt.io/browse/QTBUG-41932
            dialog.setSizeGripEnabled(True)
            dialog.setModal(True)
            dialog.show()
            return

        except Cancelled:
            return

        with self.project.apply_mutations('%s: Import audio file' % self.track.track.name):
            self.track.track.create_sample(time, loaded_sample)

    def onDeleteSample(self, smpl: model.SampleRef) -> None:
        with self.project.apply_mutations('%s: Delete segment' % self.track.track.name):
            self.track.track.delete_sample(smpl)

    def contextMenuEvent(self, evt: QtGui.QContextMenuEvent) -> None:
        time = self.track.xToTime(evt.pos().x())

        menu = QtWidgets.QMenu(self.track)
        menu.setObjectName('context-menu')

        add_sample_action = QtWidgets.QAction("Import audio file...", menu)
        add_sample_action.setObjectName('add-sample')
        add_sample_action.setStatusTip("Import an audio file and add it as a segment to the track.")
        add_sample_action.triggered.connect(functools.partial(self.onAddSampleSync, time))
        menu.addAction(add_sample_action)

        smpl = self.track.highlightedSample()
        if smpl is not None:
            delete_sample_action = QtWidgets.QAction("Delete segment", menu)
            delete_sample_action.setObjectName('delete-sample')
            delete_sample_action.setStatusTip("Remove the selected segment from the track.")
            delete_sample_action.triggered.connect(
                functools.partial(self.onDeleteSample, smpl.sample))
            menu.addAction(delete_sample_action)

        menu.popup(evt.globalPos())
        evt.accept()

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        if (evt.button() == Qt.LeftButton
                and evt.modifiers() == Qt.NoModifier
                and self.track.highlightedSample() is not None):
            self.__moving_sample = self.track.highlightedSample()
            self.__moving_sample_original_pos = self.__moving_sample.pos()
            self.__moving_sample_offset = evt.pos() - self.__moving_sample.pos()

            evt.accept()
            return

        if evt.button() == Qt.RightButton and self.__moving_sample is not None:
            self.track.setSamplePos(self.__moving_sample, self.__moving_sample_original_pos)
            self.__moving_sample = None
            evt.accept()
            return

        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        if self.__moving_sample is not None:
            new_pos = QtCore.QPoint(
                evt.pos().x() - self.__moving_sample_offset.x(),
                self.__moving_sample_original_pos.y())
            self.track.setSamplePos(self.__moving_sample, new_pos)

            evt.accept()
            return

        self.track.updateHighlightedSample()

        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        if evt.button() == Qt.LeftButton and self.__moving_sample is not None:
            pos = self.__moving_sample.pos()
            self.__moving_sample = None

            with self.project.apply_mutations('%s: Move sample' % self.track.track.name):
                self.track.highlightedSample().sample.time = self.track.xToTime(pos.x())

            evt.accept()
            return

        super().mouseReleaseEvent(evt)


class SampleTrackToolBox(tools.ToolBox):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.addTool(EditSamplesTool)


class SampleItem(core.AutoCleanupMixin, object):
    def __init__(
            self, *,
            event_loop: asyncio.AbstractEventLoop,
            track_editor: 'SampleTrackEditor',
            sample: model.SampleRef,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__event_loop = event_loop
        self.__track_editor = track_editor
        self.__sample = sample

        # For testing, triggered when all tiles have been rendered.
        self.__fully_rendered = asyncio.Event(loop=self.__event_loop)

        self.__raw_fps = []  # type: List[BinaryIO]
        self.__raws = []  # type: List[mmap.mmap]
        for ch in self.__sample.sample.channels:
            raw_path = os.path.join(
                self.__sample.project.data_dir, ch.raw_path)
            fp = open(raw_path, 'rb')
            self.__raw_fps.append(fp)
            buf = mmap.mmap(fp.fileno(), 0, prot=mmap.PROT_READ)
            self.__raws.append(buf)

        self.__tile_cache = {}  # type: Dict[Tuple[int, int], Tuple[int, QtGui.QImage]]
        self.__tile_cache_version = 0
        self.__render_queue = asyncio.Queue(loop=self.__event_loop)  # type: asyncio.Queue[Tuple]
        self.__render_task = self.__event_loop.create_task(self.__renderMain())

        self.__highlighted = False

        self.__pos = QtCore.QPoint()
        self.__width = 50
        self.__height = None  # type: int
        self.updateRect()

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)
        self.__listeners.add(self.__sample.time_changed.add(self.__onTimeChanged))

        conn = self.__track_editor.scaleXChanged.connect(self.__onScaleXChanged)
        # mypy complains about "Cannot infer type of lambda"...
        self.add_cleanup_function(
            lambda conn=conn: self.__track_editor.scaleXChanged.disconnect(conn))  # type: ignore[misc]

    def cleanup(self) -> None:
        self.__render_task.cancel()

        while self.__raws:
            self.__raws.pop(-1).close()
        while self.__raw_fps:
            self.__raw_fps.pop(-1).close()
        super().cleanup()

    @property
    def sample(self) -> model.SampleRef:
        return self.__sample

    @property
    def sample_id(self) -> int:
        return self.__sample.id

    def scaleX(self) -> fractions.Fraction:
        return self.__track_editor.scaleX()

    def width(self) -> int:
        return self.__width

    def height(self) -> int:
        return self.__track_editor.height()

    def size(self) -> QtCore.QSize:
        return QtCore.QSize(self.width(), self.height())

    def pos(self) -> QtCore.QPoint:
        return self.__pos

    def setPos(self, pos: QtCore.QPoint) -> None:
        self.__pos = pos

    def rect(self) -> QtCore.QRect:
        return QtCore.QRect(self.pos(), self.size())

    def __onTimeChanged(self, change: music.PropertyValueChange[audioproc.MusicalTime]) -> None:
        self.updateRect()
        self.__track_editor.update()

    def __onScaleXChanged(self, scale_x: fractions.Fraction) -> None:
        self.updateRect()
        self.__tile_cache.clear()
        self.purgePaintCaches()

    def updateRect(self) -> None:
        tmap = self.__track_editor.project.time_mapper

        num_samples = int(math.ceil(
            self.__sample.sample.num_samples * tmap.sample_rate / self.__sample.sample.sample_rate))

        begin_time = self.__sample.time
        begin_x = self.__track_editor.timeToX(begin_time)
        begin_samplepos = tmap.musical_to_sample_time(begin_time)
        end_samplepos = begin_samplepos + num_samples
        end_time = tmap.sample_to_musical_time(end_samplepos)
        end_x = self.__track_editor.timeToX(end_time)

        self.__pos = QtCore.QPoint(begin_x, 0)
        self.__width = end_x - begin_x

    def setHighlighted(self, highlighted: bool) -> None:
        if highlighted != self.__highlighted:
            self.__highlighted = highlighted
            self.__track_editor.update()

    def purgePaintCaches(self) -> None:
        while not self.__render_queue.empty():
            self.__render_queue.get_nowait()
        self.__tile_cache_version += 1

    # only used for tests
    def isRenderComplete(self) -> bool:
        if self.__fully_rendered.is_set():
            self.__fully_rendered.clear()
            return True
        return False

    # only used for tests
    def renderPendingCacheTiles(self) -> None:
        while not self.__render_queue.empty():
            ch, tile, size, tile_x = self.__render_queue.get_nowait()
            img = self.__renderCacheTile(ch, tile, size, tile_x)
            self.__tile_cache[(ch, tile)] = (self.__tile_cache_version, img)

    async def __renderMain(self) -> None:
        pool = concurrent.futures.ThreadPoolExecutor(1)
        try:
            while True:
                ch, tile, size, tile_x = await self.__render_queue.get()
                version = self.__tile_cache_version
                fut = pool.submit(self.__renderCacheTile, ch, tile, size, tile_x)
                await asyncio.wait_for(
                    asyncio.wrap_future(fut, loop=self.__event_loop),
                    timeout=None, loop=self.__event_loop)
                self.__tile_cache[(ch, tile)] = (version, fut.result())
                self.__track_editor.update()

        except asyncio.CancelledError:
            pass

        except Exception:  # pylint: disable=broad-except
            logger.error("Exception in SampleTrack.__renderMain():\n%s", traceback.format_exc())

        finally:
            pool.shutdown()

    def __renderCacheTile(
            self, ch: int, tile: int, size: QtCore.QSize, tile_x: int
    ) -> QtGui.QImage:
        t_start = time_lib.time()

        minmax_color = QtGui.QColor(60, 60, 60)
        rms_color = QtGui.QColor(100, 100, 180)

        img = QtGui.QImage(size, QtGui.QImage.Format_ARGB32)
        img.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(img)
        try:
            tmap = self.__sample.project.time_mapper
            begin_samplepos = tmap.musical_to_sample_time(self.__sample.time)
            num_samples = self.__sample.sample.num_samples
            duration_per_pixel = self.__track_editor.durationPerPixel()
            resample_factor = self.__sample.sample.sample_rate / tmap.sample_rate
            height = size.height()

            t0 = self.__track_editor.xToTime(tile_x)
            s0 = int((tmap.musical_to_sample_time(t0) - begin_samplepos) * resample_factor)
            for x in range(size.width()):
                t1 = t0 + duration_per_pixel
                s1 = int((tmap.musical_to_sample_time(t1) - begin_samplepos) * resample_factor)

                if 0 <= s0 < num_samples - 1:
                    cnt = max(min(num_samples, s1 + 1) - s0, 1)
                    samples = numpy.frombuffer(
                        self.__raws[ch], dtype=numpy.float32, offset=s0 * 4, count=cnt)

                    y_min = max(0, min(height - 1, int(height - samples.min() * height) // 2))
                    y_max = max(0, min(height - 1, int(height - samples.max() * height) // 2))
                    painter.fillRect(x, y_max, 1, y_min - y_max + 1, minmax_color)

                    if cnt > 10:
                        rms = numpy.sqrt(numpy.mean(samples ** 2))
                        rms_top = max(0, int(height - rms * height) // 2)
                        rms_bottom = min(height - 1, int(height + rms * height) // 2)
                        painter.fillRect(x, rms_top, 1, rms_bottom - rms_top + 1, rms_color)

                t0 = t1
                s0 = s1

        finally:
            painter.end()

        logger.debug(
            "SampleRef #%016x, channel #%d: rendered cache tile %d in %.2fms",
            self.__sample.id, ch, tile, 1000 * (time_lib.time() - t_start))

        return img

    def paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        painter.fillRect(0, 0, 1, self.height(), QtGui.QColor(0, 0, 0))
        if self.__highlighted:
            painter.fillRect(
                1, 0, self.width() - 1, self.height(), QtGui.QColor(255, 255, 255, 150))
        else:
            painter.fillRect(
                1, 0, self.width() - 1, self.height(), QtGui.QColor(255, 255, 255, 100))
        painter.fillRect(self.width() - 1, 0, 1, self.height(), QtGui.QColor(0, 0, 0))

        if self.__height != self.__track_editor.height():
            self.__height = self.__track_editor.height()
            self.__tile_cache_version += 1

        while not self.__render_queue.empty():
            ch, tile, _, _ = self.__render_queue.get_nowait()

        render_requests = []
        num_channels = len(self.__sample.sample.channels)
        channel_top = 0
        for ch in range(num_channels):
            channel_bottom = int((ch + 1) * self.height() / num_channels)
            channel_height = channel_bottom - channel_top
            channel_zero = (channel_top + channel_bottom) // 2

            if ch != 0:
                painter.fillRect(0, channel_top, self.width(), 1, QtGui.QColor(150, 150, 150))
            painter.fillRect(0, channel_zero, self.width(), 1, QtGui.QColor(0, 0, 0))

            TILE_WIDTH = 400
            tile = paint_rect.left() // TILE_WIDTH
            tile_x = tile * TILE_WIDTH
            while tile_x < paint_rect.right():
                tile_x = tile * TILE_WIDTH

                tile_key = (ch, tile)
                version, tile_img = self.__tile_cache.get(tile_key, (-1, None))

                if version != self.__tile_cache_version or tile_img is None:
                    render_requests.append(
                        (ch, tile, QtCore.QSize(TILE_WIDTH, channel_height),
                         self.__pos.x() + tile_x))

                tile_rect = QtCore.QRect(tile_x, channel_top, TILE_WIDTH, channel_height)
                if tile_img is not None:
                    painter.drawImage(tile_rect, tile_img, tile_img.rect())
                else:
                    painter.fillRect(tile_rect, QtGui.QColor(100, 100, 100, 100))

                tile += 1
                tile_x += TILE_WIDTH

            channel_top = channel_bottom

        if render_requests:
            random.shuffle(render_requests)
            for ch, tile, size, tile_x in render_requests:
                self.__render_queue.put_nowait((ch, tile, size, tile_x))

        else:
            self.__fully_rendered.set()


class SampleTrackEditor(time_view_mixin.ContinuousTimeMixin, base_track_editor.BaseTrackEditor):
    def __init__(self, **kwargs: Any) -> None:
        self.__samples = []  # type: List[SampleItem]

        super().__init__(**kwargs)

        self.__listeners = core.ListenerList()
        self.add_cleanup_function(self.__listeners.cleanup)

        self.__playback_time = None  # type: audioproc.MusicalTime
        self.__highlighted_sample = None  # type: SampleItem
        self.__mouse_pos = None  # type: QtCore.QPoint

        for sample in self.track.samples:
            self.addSample(len(self.__samples), sample)

        self.__listeners.add(self.track.samples_changed.add(self.onSamplesChanged))
        self.__listeners.add(self.project.time_mapper_changed.add(self.__timeMapperChanged))

        self.playbackPositionChanged.connect(self.__playbackPositionChanged)

        self.setDefaultHeight(120)

    @property
    def track(self) -> model.SampleTrack:
        return down_cast(model.SampleTrack, super().track)

    def sample(self, idx: int) -> SampleItem:
        return self.__samples[idx]

    def cleanup(self) -> None:
        for item in self.__samples:
            item.cleanup()
        self.__samples.clear()

        super().cleanup()

    def createToolBox(self) -> SampleTrackToolBox:
        return SampleTrackToolBox(track=self, context=self.context)

    def onSamplesChanged(self, change: music.PropertyListChange[model.SampleRef]) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.addSample(change.index, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.removeSample(change.index, change.old_value)

        else:
            raise TypeError(type(change))

    def addSample(self, insert_index: int, sample: model.SampleRef) -> None:
        item = SampleItem(event_loop=self.event_loop, track_editor=self, sample=sample)
        self.__samples.insert(insert_index, item)
        self.update()

    def removeSample(self, remove_index: int, sample: model.SampleRef) -> None:
        item = self.__samples.pop(remove_index)
        item.cleanup()
        self.update()

    def __timeMapperChanged(self) -> None:
        self.purgePaintCaches()
        for item in self.__samples:
            item.updateRect()
        self.update()

    def __playbackPositionChanged(self, time: audioproc.MusicalTime) -> None:
        if self.__playback_time is not None:
            x = self.timeToX(self.__playback_time)
            self.update(x - self.xOffset(), 0, 2, self.height())

        self.__playback_time = time

        if self.__playback_time is not None:
            x = self.timeToX(self.__playback_time)
            self.update(x - self.xOffset(), 0, 2, self.height())

    def setHighlightedSample(self, sample: SampleItem) -> None:
        if sample is self.__highlighted_sample:
            return

        if self.__highlighted_sample is not None:
            self.__highlighted_sample.setHighlighted(False)
            self.__highlighted_sample = None

        if sample is not None:
            sample.setHighlighted(True)
            self.__highlighted_sample = sample

    def highlightedSample(self) -> SampleItem:
        return self.__highlighted_sample

    def updateHighlightedSample(self) -> None:
        if self.__mouse_pos is None:
            self.setHighlightedSample(None)
            return

        mx = self.__mouse_pos.x() + self.xOffset()
        closest_sample = None  # type: SampleItem
        closest_dist = None  # type: int
        for sample in self.__samples:
            if mx < sample.pos().x():
                dist = sample.pos().x() - mx
            elif mx > sample.pos().x() + sample.width():
                dist = mx - (sample.pos().x() + sample.width())
            else:
                dist = 0

            if dist < 20 and (closest_dist is None or dist < closest_dist):
                closest_dist = dist
                closest_sample = sample

        self.setHighlightedSample(closest_sample)

    def setSamplePos(self, sample: SampleItem, pos: QtCore.QPoint) -> None:
        sample.setPos(pos)
        self.update()

    def leaveEvent(self, evt: QtCore.QEvent) -> None:
        self.__mouse_pos = None
        self.setHighlightedSample(None)
        super().leaveEvent(evt)

    def mousePressEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()
        super().mousePressEvent(evt)

    def mouseMoveEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()
        super().mouseMoveEvent(evt)

    def mouseReleaseEvent(self, evt: QtGui.QMouseEvent) -> None:
        self.__mouse_pos = evt.pos()
        super().mouseReleaseEvent(evt)

    def purgePaintCaches(self) -> None:
        super().purgePaintCaches()
        for item in self.__samples:
            item.purgePaintCaches()

    def _paint(self, painter: QtGui.QPainter, paint_rect: QtCore.QRect) -> None:
        self.renderTimeGrid(painter, paint_rect)

        for item in self.__samples:
            sample_rect = item.rect().intersected(paint_rect)
            if not sample_rect.isEmpty():
                painter.save()
                try:
                    painter.setClipRect(sample_rect)
                    painter.translate(item.pos())
                    item.paint(painter, sample_rect.translated(-item.pos()))
                finally:
                    painter.restore()

        if self.__playback_time is not None:
            pos = self.timeToX(self.__playback_time)
            painter.fillRect(pos, 0, 2, self.height(), QtGui.QColor(0, 0, 160))
