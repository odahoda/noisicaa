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

# TODO: pylint-unclean

from fractions import Fraction
import logging
import random

import numpy

from noisicaa import core
from noisicaa import audioproc
from noisicaa.bindings import sndfile

from . import model
from . import state
from . import commands
from . import base_track
from . import pipeline_graph
from . import misc

logger = logging.getLogger(__name__)


class AddSample(commands.Command):
    time = core.Property(audioproc.MusicalTime)
    path = core.Property(str)

    def __init__(self, time=None, path=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.time = time
            self.path = path

    def run(self, track):
        assert isinstance(track, SampleTrack)

        project = track.project

        smpl = Sample(path=self.path)
        project.samples.append(smpl)

        smpl_ref = SampleRef(time=self.time, sample_id=smpl.id)
        track.samples.append(smpl_ref)

commands.Command.register_command(AddSample)


class RemoveSample(commands.Command):
    sample_id = core.Property(str)

    def __init__(self, sample_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.sample_id = sample_id

    def run(self, track):
        assert isinstance(track, SampleTrack)

        root = track.root
        smpl_ref = root.get_object(self.sample_id)
        assert smpl_ref.is_child_of(track)

        del track.samples[smpl_ref.index]

commands.Command.register_command(RemoveSample)


class MoveSample(commands.Command):
    sample_id = core.Property(str)
    time = core.Property(audioproc.MusicalTime)

    def __init__(self, sample_id=None, time=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.sample_id = sample_id
            self.time = time

    def run(self, track):
        assert isinstance(track, SampleTrack)

        root = track.root
        smpl_ref = root.get_object(self.sample_id)
        assert smpl_ref.is_child_of(track)

        smpl_ref.time = self.time

commands.Command.register_command(MoveSample)


class RenderSample(commands.Command):
    scale_x = core.Property(Fraction)

    def __init__(self, scale_x=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.scale_x = scale_x

    def run(self, sample_ref):
        assert isinstance(sample_ref, SampleRef)

        root = sample_ref.root
        sample = root.get_object(sample_ref.sample_id)

        try:
            samples = sample.samples
        except sndfile.Error:
            return ['broken']

        samples = sample.samples[...,0]

        tmap = audioproc.TimeMapper()
        try:
            tmap.setup(sample.project)

            begin_time = sample_ref.time
            begin_samplepos = tmap.musical_to_sample_time(begin_time)
            num_samples = min(tmap.num_samples - begin_samplepos, len(samples))
            end_samplepos = begin_samplepos + num_samples
            end_time = tmap.sample_to_musical_time(end_samplepos)

        finally:
            tmap.cleanup()

        width = int(self.scale_x * (end_time - begin_time).fraction)

        if width < num_samples / 10:
            rms = []
            for p in range(0, width):
                p_start = p * num_samples // width
                p_end = (p + 1) * num_samples // width
                s = samples[p_start:p_end]
                rms.append(numpy.sqrt(numpy.mean(numpy.square(s))))

            return ['rms', rms]

        else:
            return ['broken']

commands.Command.register_command(RenderSample)


class Sample(model.Sample, state.StateBase):
    def __init__(self, path=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.path = path

        self._samples = None

    @property
    def samples(self):
        if self._samples is None:
            with sndfile.SndFile(self.path) as sf:
                self._samples = sf.get_samples()
        return self._samples

state.StateBase.register_class(Sample)


class SampleRef(model.SampleRef, state.StateBase):
    def __init__(self, time=None, sample_id=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.time = time
            self.sample_id = sample_id

state.StateBase.register_class(SampleRef)


class SampleTrackConnector(base_track.TrackConnector):
    def __init__(self, *, node_id, **kwargs):
        super().__init__(**kwargs)

        self.__node_id = node_id
        self.__listeners = {}
        self.__sample_ids = {}

    def _init_internal(self):
        for sample_ref in self._track.samples:
            self.__add_sample(sample_ref)

        self.__listeners['samples'] = self._track.listeners.add(
            'samples', self.__samples_list_changed)

    def close(self):
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __samples_list_changed(self, change):
        if isinstance(change, core.PropertyListInsert):
            self.__add_sample(change.new_value)

        elif isinstance(change, core.PropertyListDelete):
            self.__remove_sample(change.old_value)

        else:  # pragma: no coverage
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def __add_sample(self, sample_ref):
        sample_id = self.__sample_ids[sample_ref.id] = random.getrandbits(64)

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                sample_script_add_sample=audioproc.ProcessorMessage.SampleScriptAddSample(
                    id=sample_id,
                    time=sample_ref.time.to_proto(),
                    sample_path=sample_ref.sample.path)))

        self.__listeners['cp:%s:time' % sample_ref.id] = sample_ref.listeners.add(
            'time', lambda _: self.__sample_changed(sample_ref))

        self.__listeners['cp:%s:sample_id' % sample_ref.id] = sample_ref.listeners.add(
            'sample_id', lambda _: self.__sample_changed(sample_ref))

    def __remove_sample(self, sample_ref):
        sample_id = self.__sample_ids[sample_ref.id]

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                sample_script_remove_sample=audioproc.ProcessorMessage.SampleScriptRemoveSample(
                    id=sample_id)))

        self.__listeners.pop('cp:%s:time' % sample_ref.id).remove()
        self.__listeners.pop('cp:%s:sample_id' % sample_ref.id).remove()

    def __sample_changed(self, sample_ref):
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


class SampleTrack(model.SampleTrack, base_track.Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def create_track_connector(self, **kwargs):
        return SampleTrackConnector(
            track=self,
            node_id=self.sample_script_name,
            **kwargs)

    @property
    def sample_script_name(self):
        return '%s-samplescript' % self.id

    @property
    def sample_script_node(self):
        if self.sample_script_id is None:
            raise ValueError("No samplescript node found.")

        return self.root.get_object(self.sample_script_id)

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        sample_script_node = pipeline_graph.SampleScriptPipelineGraphNode(
            name="Sample Script",
            graph_pos=mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(sample_script_node)
        self.sample_script_id = sample_script_node.id

        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                sample_script_node, 'out:left', mixer_node, 'in:left'))
        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                sample_script_node, 'out:right', mixer_node, 'in:right'))

    def remove_pipeline_nodes(self):
        self.project.remove_pipeline_graph_node(self.sample_script_node)
        self.sample_script_id = None
        super().remove_pipeline_nodes()


state.StateBase.register_class(SampleTrack)
