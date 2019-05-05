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

import fractions
import logging
import random
from typing import Any, Dict, MutableSequence, Optional, Callable

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model_base
from noisicaa import core
from noisicaa import node_db
from noisicaa.bindings import sndfile
from noisicaa.music import node_connector
from noisicaa.music import model
from noisicaa.music import base_track
from noisicaa.music import rms
from noisicaa.music import samples as samples_lib
from noisicaa.builtin_nodes import model_registry_pb2
from . import ipc_pb2
from . import processor_messages
from . import node_description

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
        self.__listeners = {}  # type: Dict[str, core.Listener]
        self.__sample_ids = {}  # type: Dict[int, int]

    def _init_internal(self) -> None:
        for sample_ref in self._node.samples:
            self.__add_sample(sample_ref)

        self.__listeners['samples'] = self._node.samples_changed.add(
            self.__samples_list_changed)

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __samples_list_changed(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.__add_sample(change.new_value)

        elif isinstance(change, model_base.PropertyListDelete):
            self.__remove_sample(change.old_value)

        else:  # pragma: no coverage
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_sample(self, sample_ref: 'SampleRef') -> None:
        sample_id = self.__sample_ids[sample_ref.id] = random.getrandbits(64)

        self._emit_message(processor_messages.add_sample(
            node_id=self.__node_id,
            id=sample_id,
            time=sample_ref.time,
            sample_path=sample_ref.sample.path))

        self.__listeners['cp:%s:time' % sample_ref.id] = sample_ref.time_changed.add(
            lambda _: self.__sample_changed(sample_ref))

        self.__listeners['cp:%s:sample' % sample_ref.id] = sample_ref.sample_changed.add(
            lambda _: self.__sample_changed(sample_ref))

    def __remove_sample(self, sample_ref: 'SampleRef') -> None:
        sample_id = self.__sample_ids[sample_ref.id]

        self._emit_message(processor_messages.remove_sample(
            node_id=self.__node_id,
            id=sample_id))

        self.__listeners.pop('cp:%s:time' % sample_ref.id).remove()
        self.__listeners.pop('cp:%s:sample' % sample_ref.id).remove()

    def __sample_changed(self, sample_ref: 'SampleRef') -> None:
        sample_id = self.__sample_ids[sample_ref.id]

        self._emit_message(processor_messages.remove_sample(
            node_id=self.__node_id,
            id=sample_id))
        self._emit_message(processor_messages.add_sample(
            node_id=self.__node_id,
            id=sample_id,
            time=sample_ref.time,
            sample_path=sample_ref.sample.path))


class SampleRef(model.ProjectChild):
    class SampleRefSpec(model_base.ObjectSpec):
        proto_type = 'sample_ref'
        proto_ext = model_registry_pb2.sample_ref

        time = model_base.WrappedProtoProperty(audioproc.MusicalTime)
        sample = model_base.ObjectReferenceProperty(samples_lib.Sample)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = core.Callback[model_base.PropertyChange[audioproc.MusicalTime]]()
        self.sample_changed = core.Callback[model_base.PropertyChange[samples_lib.Sample]]()

    def create(
            self, *,
            time: Optional[audioproc.MusicalTime] = None,
            sample: Optional[samples_lib.Sample] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.sample = sample

    @property
    def time(self) -> audioproc.MusicalTime:
        return self.get_property_value('time')

    @time.setter
    def time(self, value: audioproc.MusicalTime) -> None:
        self.set_property_value('time', value)

    @property
    def sample(self) -> samples_lib.Sample:
        return self.get_property_value('sample')

    @sample.setter
    def sample(self, value: samples_lib.Sample) -> None:
        self.set_property_value('sample', value)


class SampleTrack(base_track.Track):
    class SampleTrackSpec(model_base.ObjectSpec):
        proto_type = 'sample_track'
        proto_ext = model_registry_pb2.sample_track

        samples = model_base.ObjectListProperty(SampleRef)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.samples_changed = core.Callback[model_base.PropertyListChange[SampleRef]]()

    @property
    def samples(self) -> MutableSequence[SampleRef]:
        return self.get_property_value('samples')

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> SampleTrackConnector:
        return SampleTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.SampleTrackDescription

    def create_sample(self, time: audioproc.MusicalTime, path: str) -> SampleRef:
        smpl = self._pool.create(samples_lib.Sample, path=path)
        self.project.samples.append(smpl)

        smpl_ref = self._pool.create(
            SampleRef,
            time=time,
            sample=smpl)
        self.samples.append(smpl_ref)
        return smpl_ref

    def delete_sample(self, smpl_ref: SampleRef) -> None:
        del self.samples[smpl_ref.index]
