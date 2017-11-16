#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from fractions import Fraction
import logging

import numpy

from noisicaa import core
from noisicaa import audioproc
from noisicaa.bindings import sndfile

from .time import Duration
from . import model
from . import state
from . import commands
from . import mutations
from . import base_track
from . import pipeline_graph
from . import misc
from . import time_mapper

logger = logging.getLogger(__name__)


class AddSample(commands.Command):
    timepos = core.Property(Duration)
    path = core.Property(str)

    def __init__(self, timepos=None, path=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.timepos = timepos
            self.path = path

    def run(self, track):
        assert isinstance(track, SampleTrack)

        project = track.project

        smpl = Sample(path=self.path)
        project.samples.append(smpl)

        smpl_ref = SampleRef(timepos=self.timepos, sample_id=smpl.id)
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
    timepos = core.Property(Duration)

    def __init__(self, sample_id=None, timepos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.sample_id = sample_id
            self.timepos = timepos

    def run(self, track):
        assert isinstance(track, SampleTrack)

        root = track.root
        smpl_ref = root.get_object(self.sample_id)
        assert smpl_ref.is_child_of(track)

        smpl_ref.timepos = self.timepos

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

        tmap = time_mapper.TimeMapper(sample.project)

        begin_timepos = sample_ref.timepos
        begin_samplepos = tmap.timepos2sample(begin_timepos)
        num_samples = min(tmap.total_duration_samples - begin_samplepos, len(samples))
        end_samplepos = begin_samplepos + num_samples
        end_timepos = tmap.sample2timepos(end_samplepos)

        width = int(self.scale_x * (end_timepos - begin_timepos))

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
    def __init__(self, timepos=None, sample_id=None, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            self.timepos = timepos
            self.sample_id = sample_id

state.StateBase.register_class(SampleRef)


class SampleBufferSource(base_track.BufferSource):
    def __init__(self, track):
        super().__init__(track)

        self.time_mapper = time_mapper.TimeMapper(self._project)

    def get_buffers(self, ctxt):
        output = numpy.zeros(shape=(ctxt.block_size, 2), dtype=numpy.float32)

        buffer_left_id = 'track:%s:left' % self._track.id
        try:
            buffer_left = ctxt.buffers[buffer_left_id]
        except KeyError:
            pass
        else:
            # Copy events from existing buffer.
            output[:ctxt.offset,0] = numpy.frombuffer(
                buffer_left.data, count=ctxt.offset, dtype=numpy.float32)

        buffer_right_id = 'track:%s:right' % self._track.id
        try:
            buffer_right = ctxt.buffers[buffer_right_id]
        except KeyError:
            pass
        else:
            # Copy events from existing buffer.
            output[:ctxt.offset,1] = numpy.frombuffer(
                buffer_right.data, count=ctxt.offset, dtype=numpy.float32)

        f1 = ctxt.sample_pos
        f2 = ctxt.sample_pos + ctxt.length

        for sample_ref in self._track.samples:
            s1 = self.time_mapper.timepos2sample(sample_ref.timepos)
            if s1 >= f2:
                continue

            sample = self._track.root.get_object(sample_ref.sample_id)
            samples = sample.samples
            assert len(samples.shape) == 2, samples.shape
            assert samples.shape[1] in (1, 2), samples.shape

            s2 = s1 + samples.shape[0]
            if s2 <= f1:
                continue

            if f1 >= s1:
                src = f1 - s1
                dest = ctxt.offset
                length = min(ctxt.length, s2 - f1)
            else:
                src = 0
                dest = s1 - f1 + ctxt.offset
                length = min(s2, f2) - s1

            for ch in range(2):
                output[dest:dest+length,ch] = samples[src:src+length,ch % samples.shape[1]]

        samples_left = output[:,0].tobytes()
        buffer_left = audioproc.Buffer.new_message()
        buffer_left.id = buffer_left_id
        buffer_left.data = bytes(samples_left)
        ctxt.buffers[buffer_left_id] = buffer_left

        samples_right = output[:,1].tobytes()
        buffer_right = audioproc.Buffer.new_message()
        buffer_right.id = buffer_right_id
        buffer_right.data = bytes(samples_right)
        ctxt.buffers[buffer_right_id] = buffer_right


class SampleTrack(model.SampleTrack, base_track.Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def create_buffer_source(self):
        return SampleBufferSource(self)

    @property
    def audio_source_name(self):
        return '%s-control' % self.id

    @property
    def audio_source_node(self):
        if self.audio_source_id is None:
            raise ValueError("No audio source node found.")

        return self.root.get_object(self.audio_source_id)

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        audio_source_node = pipeline_graph.AudioSourcePipelineGraphNode(
            name="Audio Source",
            graph_pos=mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(audio_source_node)
        self.audio_source_id = audio_source_node.id

        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                audio_source_node, 'out:left', mixer_node, 'in:left'))
        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                audio_source_node, 'out:right', mixer_node, 'in:right'))

    def remove_pipeline_nodes(self):
        self.project.remove_pipeline_graph_node(self.audio_source_node)
        self.audio_source_id = None
        super().remove_pipeline_nodes()


state.StateBase.register_class(SampleTrack)
