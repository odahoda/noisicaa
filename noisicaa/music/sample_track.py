#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import Any, List, Optional, Dict, Iterator, Callable

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa import core
from noisicaa.bindings import sndfile
from . import pmodel
from . import node_connector
from . import base_track
from . import commands
from . import commands_pb2
from . import rms

logger = logging.getLogger(__name__)


class AddSample(commands.Command):
    proto_type = 'add_sample'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.AddSample, pb)
        track = down_cast(pmodel.SampleTrack, pool[self.proto.command.target])

        smpl = pool.create(Sample, path=pb.path)
        project.samples.append(smpl)

        smpl_ref = pool.create(
            SampleRef,
            time=audioproc.MusicalTime.from_proto(pb.time),
            sample=smpl)
        track.samples.append(smpl_ref)

commands.Command.register_command(AddSample)


class RemoveSample(commands.Command):
    proto_type = 'remove_sample'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveSample, pb)
        track = down_cast(pmodel.SampleTrack, pool[self.proto.command.target])

        smpl_ref = down_cast(pmodel.SampleRef, pool[pb.sample_id])
        assert smpl_ref.is_child_of(track)

        del track.samples[smpl_ref.index]

commands.Command.register_command(RemoveSample)


class MoveSample(commands.Command):
    proto_type = 'move_sample'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.MoveSample, pb)
        track = down_cast(pmodel.SampleTrack, pool[self.proto.command.target])

        smpl_ref = down_cast(pmodel.SampleRef, pool[pb.sample_id])
        assert smpl_ref.is_child_of(track)

        smpl_ref.time = audioproc.MusicalTime.from_proto(pb.time)

commands.Command.register_command(MoveSample)


class RenderSample(commands.Command):
    proto_type = 'render_sample'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> List[Any]:
        pb = down_cast(commands_pb2.RenderSample, pb)
        sample_ref = down_cast(pmodel.SampleRef, pool[self.proto.command.target])
        sample = down_cast(Sample, sample_ref.sample)

        try:
            samples = sample.samples
        except sndfile.Error:
            return ['broken']

        samples = sample.samples[..., 0]  # type: ignore

        tmap = audioproc.TimeMapper(44100)
        try:
            tmap.setup(sample.project)

            begin_time = sample_ref.time
            begin_samplepos = tmap.musical_to_sample_time(begin_time)
            num_samples = min(tmap.num_samples - begin_samplepos, len(samples))
            end_samplepos = begin_samplepos + num_samples
            end_time = tmap.sample_to_musical_time(end_samplepos)

        finally:
            tmap.cleanup()

        scale_x = fractions.Fraction(pb.scale_x.numerator, pb.scale_x.denominator)
        width = int(scale_x * (end_time - begin_time).fraction)

        if width < num_samples / 10:
            result = []
            for p in range(0, width):
                p_start = p * num_samples // width
                p_end = (p + 1) * num_samples // width
                s = samples[p_start:p_end]
                result.append(rms.rms(s))

            return ['rms', result]

        else:
            return ['broken']

commands.Command.register_command(RenderSample)


class Sample(pmodel.Sample):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._samples = None  # type: memoryview

    def create(self, *, path: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.path = path

    @property
    def samples(self) -> memoryview:
        if self._samples is None:
            with sndfile.SndFile(self.path) as sf:
                self._samples = sf.get_samples()
        return self._samples


class SampleRef(pmodel.SampleRef):
    def create(
            self, *,
            time: Optional[audioproc.MusicalTime] = None, sample: Optional[Sample] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.sample = sample


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

    def __samples_list_changed(self, change: model.PropertyChange) -> None:
        if isinstance(change, model.PropertyListInsert):
            self.__add_sample(change.new_value)

        elif isinstance(change, model.PropertyListDelete):
            self.__remove_sample(change.old_value)

        else:  # pragma: no coverage
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_sample(self, sample_ref: pmodel.SampleRef) -> None:
        sample_id = self.__sample_ids[sample_ref.id] = random.getrandbits(64)

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                sample_script_add_sample=audioproc.ProcessorMessage.SampleScriptAddSample(
                    id=sample_id,
                    time=sample_ref.time.to_proto(),
                    sample_path=sample_ref.sample.path)))

        self.__listeners['cp:%s:time' % sample_ref.id] = sample_ref.time_changed.add(
            lambda _: self.__sample_changed(sample_ref))

        self.__listeners['cp:%s:sample' % sample_ref.id] = sample_ref.sample_changed.add(
            lambda _: self.__sample_changed(sample_ref))

    def __remove_sample(self, sample_ref: pmodel.SampleRef) -> None:
        sample_id = self.__sample_ids[sample_ref.id]

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                sample_script_remove_sample=audioproc.ProcessorMessage.SampleScriptRemoveSample(
                    id=sample_id)))

        self.__listeners.pop('cp:%s:time' % sample_ref.id).remove()
        self.__listeners.pop('cp:%s:sample' % sample_ref.id).remove()

    def __sample_changed(self, sample_ref: pmodel.SampleRef) -> None:
        sample_id = self.__sample_ids[sample_ref.id]

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                sample_script_remove_sample=audioproc.ProcessorMessage.SampleScriptRemoveSample(
                    id=sample_id)))
        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                sample_script_add_sample=audioproc.ProcessorMessage.SampleScriptAddSample(
                    id=sample_id,
                    time=sample_ref.time.to_proto(),
                    sample_path=sample_ref.sample.path)))


class SampleTrack(pmodel.SampleTrack, base_track.Track):
    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> SampleTrackConnector:
        return SampleTrackConnector(node=self, message_cb=message_cb)

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)
