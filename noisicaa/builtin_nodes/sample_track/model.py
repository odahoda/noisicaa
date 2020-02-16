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

import base64
import fractions
import logging
import os
import os.path
import time as time_lib
from typing import Any, Optional, Callable

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import music
from noisicaa import core
from noisicaa import node_db
from noisicaa.bindings import sndfile
from noisicaa.music import node_connector
from noisicaa.music import rms
from noisicaa.music import samples as samples_lib
from . import ipc_pb2
from . import processor_messages
from . import node_description
from . import _model

logger = logging.getLogger(__name__)


async def render_sample(
        sample_ref: 'SampleRef',
        scale_x: fractions.Fraction,
) -> ipc_pb2.RenderSampleResponse:
    response = ipc_pb2.RenderSampleResponse()

    sample = down_cast(samples_lib.Sample, sample_ref.sample)

    try:
        smpls = sample.samples
    except sndfile.Error:
        response.broken = True
        return response

    smpls = sample.samples[..., 0]  # type: ignore

    tmap = audioproc.TimeMapper(44100)
    try:
        tmap.setup(sample.project)

        begin_time = sample_ref.time
        begin_samplepos = tmap.musical_to_sample_time(begin_time)
        num_samples = min(tmap.num_samples - begin_samplepos, len(smpls))
        end_samplepos = begin_samplepos + num_samples
        end_time = tmap.sample_to_musical_time(end_samplepos)

    finally:
        tmap.cleanup()

    width = int(scale_x * (end_time - begin_time).fraction)

    if width < num_samples / 10:
        for p in range(0, width):
            p_start = p * num_samples // width
            p_end = (p + 1) * num_samples // width
            s = smpls[p_start:p_end]
            response.rms.append(rms.rms(s))

    else:
        response.broken = True

    return response


class SampleTrackConnector(node_connector.NodeConnector):
    _node = None  # type: SampleTrack

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

    def _init_internal(self) -> None:
        for sample_ref in self._node.samples:
            self.__add_sample(sample_ref)

        self.__listeners['samples'] = self._node.samples_changed.add(
            self.__samples_list_changed)

    def __samples_list_changed(self, change: music.PropertyChange) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__add_sample(change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__remove_sample(change.old_value)

        else:  # pragma: no coverage
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_sample(self, sample_ref: 'SampleRef') -> None:
        self._emit_message(processor_messages.add_sample(
            node_id=self.__node_id,
            id=sample_ref.id,
            time=sample_ref.time,
            sample_rate=sample_ref.sample.sample_rate,
            num_samples=sample_ref.sample.num_samples,
            channel_paths=[
                os.path.join(self._node.project.data_dir, channel.raw_path)
                for channel in sample_ref.sample.channels]))

        self.__listeners['cp:%s:time' % sample_ref.id] = sample_ref.time_changed.add(
            lambda _: self.__sample_changed(sample_ref))

        self.__listeners['cp:%s:sample' % sample_ref.id] = sample_ref.sample_changed.add(
            lambda _: self.__sample_changed(sample_ref))

    def __remove_sample(self, sample_ref: 'SampleRef') -> None:
        self._emit_message(processor_messages.remove_sample(
            node_id=self.__node_id,
            id=sample_ref.id))

        del self.__listeners['cp:%s:time' % sample_ref.id]
        del self.__listeners['cp:%s:sample' % sample_ref.id]

    def __sample_changed(self, sample_ref: 'SampleRef') -> None:
        self._emit_message(processor_messages.remove_sample(
            node_id=self.__node_id,
            id=sample_ref.id))
        self._emit_message(processor_messages.add_sample(
            node_id=self.__node_id,
            id=sample_ref.id,
            time=sample_ref.time,
            sample_rate=sample_ref.sample.sample_rate,
            num_samples=sample_ref.sample.num_samples,
            channel_paths=[
                os.path.join(self._node.project.data_dir, channel.raw_path)
                for channel in sample_ref.sample.channels]))


class SampleRef(_model.SampleRef):
    def create(
            self, *,
            time: Optional[audioproc.MusicalTime] = None,
            sample: Optional[samples_lib.Sample] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.sample = sample


class SampleTrack(_model.SampleTrack):
    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> SampleTrackConnector:
        return SampleTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.SampleTrackDescription

    def create_sample(
            self,
            time: audioproc.MusicalTime,
            path: str,
            *,
            progress_cb: Callable[[float], None] = None
    ) -> SampleRef:
        sample_name_base = base64.b32encode(os.urandom(15)).decode('ascii')
        sample_path_base = os.path.join('samples', sample_name_base)

        os.makedirs(
            os.path.dirname(os.path.join(self.project.data_dir, sample_path_base)),
            exist_ok=True)

        logger.info("Importing sample from '%s' as '%s'...", path, sample_name_base)
        t0 = time_lib.time()
        next_progress = t0 + 0.5
        with sndfile.SndFile(path) as sf:
            logger.info("Sample rate: %d", sf.sample_rate)
            logger.info("Num samples: %d", sf.num_samples)
            logger.info("Num channels: %d", sf.num_channels)

            raw_paths = [
                sample_path_base + '-ch%02d.raw' % ch
                for ch in range(sf.num_channels)]
            raw_fps = []
            try:
                for raw_path in raw_paths:
                    raw_path = os.path.join(self.project.data_dir, raw_path)
                    raw_fps.append(open(raw_path, 'wb'))

                samples_read = 0
                while True:
                    data = sf.read_samples(10240)
                    if len(data) == 0:
                        break
                    samples_read += len(data)

                    data = data.transpose()
                    assert len(data) == len(raw_fps)
                    for fp, samples in zip(raw_fps, data):
                        fp.write(samples.tobytes('C'))

                    if progress_cb is not None and time_lib.time() >= next_progress:
                        progress_cb(float(samples_read) / sf.num_samples)
                        next_progress = time_lib.time() + 0.1

                if samples_read != sf.num_samples:
                    raise ValueError(
                        "Failed to read all samples (%d != %d)" % (samples_read, sf.num_samples))

            except:
                for raw_path in raw_paths:
                    raw_path = os.path.join(self.project.data_dir, raw_path)
                    if os.path.exists(raw_path):
                        os.unlink(raw_path)
                raise

            finally:
                for fp in raw_fps:
                    fp.close()

            logger.info("Sample imported in %.3fsec", time_lib.time() - t0)

            smpl = self._pool.create(
                samples_lib.Sample,
                path=path,
                sample_rate=sf.sample_rate,
                num_samples=sf.num_samples)
            for raw_path in raw_paths:
                smpl_channel = self._pool.create(samples_lib.SampleChannel, raw_path=raw_path)
                smpl.channels.append(smpl_channel)
            self.project.samples.append(smpl)

            smpl_ref = self._pool.create(
                SampleRef,
                time=time,
                sample=smpl)
            self.samples.append(smpl_ref)

        return smpl_ref

    def delete_sample(self, smpl_ref: SampleRef) -> None:
        del self.samples[smpl_ref.index]
