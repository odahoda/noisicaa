#!/usr/bin/python3

from fractions import Fraction
import logging

import numpy

from noisicaa import core
from noisicaa import audioproc
from noisicaa.bindings import sndfile

from .track import Track
from .time import Duration
from . import model
from . import state
from . import commands
from . import mutations
from . import track
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

        sheet = track.sheet

        smpl = Sample(path=self.path)
        sheet.samples.append(smpl)

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

        tmap = time_mapper.TimeMapper(sample.sheet)

        begin_timepos = sample_ref.timepos
        begin_samplepos = tmap.timepos2sample(begin_timepos)
        end_samplepos = begin_samplepos + len(samples)
        end_timepos = tmap.sample2timepos(end_samplepos)

        width = int(self.scale_x * (end_timepos - begin_timepos))

        print(begin_samplepos, end_samplepos, begin_timepos, end_timepos, self.scale_x, width)

        if width < len(samples) / 10:
            rms = []
            for p in range(0, width):
                p_start = p * len(samples) // width
                p_end = (p + 1) * len(samples) // width
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


class SampleEntitySource(track.EntitySource):
    def __init__(self, track):
        super().__init__(track)

        self.time_mapper = time_mapper.TimeMapper(self._sheet)

    def get_entities(self, frame_data, sample_pos_offset):
        # entity = audioproc.ControlFrameEntity()

        # if len(self._track.points) > 0:
        #     sample_pos = frame_data.sample_pos - sample_pos_offset

        #     timepos = self.time_mapper.sample2timepos(
        #         sample_pos % self.time_mapper.total_duration_samples)
        #     for point in self._track.points:
        #         if timepos <= point.timepos:
        #             if point.is_first:
        #                 entity.frame = numpy.full(
        #                     frame_data.duration, point.value, dtype=numpy.float32)
        #             else:
        #                 prev = point.prev_sibling

        #                 # TODO: don't use a constant value per frame,
        #                 # compute control value at a-rate.
        #                 value = (
        #                     prev.value
        #                     + (timepos - prev.timepos)
        #                     * (point.value - prev.value)
        #                     / (point.timepos - prev.timepos))
        #                 entity.frame = numpy.full(
        #                     frame_data.duration, value, dtype=numpy.float32)
        #             break
        #     else:
        #         entity.frame = numpy.full(
        #             frame_data.duration, self._track.points[-1].value, dtype=numpy.float32)

        # else:
        #     entity.frame = numpy.zeros(frame_data.duration, dtype=numpy.float32)

        # frame_data.entities['track:%s' % self._track.id] = entity
        pass


class SampleTrack(model.SampleTrack, Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def create_entity_source(self):
        return SampleEntitySource(self)

    @property
    def mixer_name(self):
        return self.parent_mixer_name

    @property
    def mixer_node(self):
        return self.parent_mixer_node

    @property
    def audio_source_name(self):
        return '%s-control' % self.id

    @property
    def audio_source_node(self):
        if self.audio_source_id is None:
            raise ValueError("No audio source node found.")

        return self.root.get_object(self.audio_source_id)

    def add_pipeline_nodes(self):
        audio_source_node = pipeline_graph.AudioSourcePipelineGraphNode(
            name="Audio Source",
            graph_pos=self.parent_mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(audio_source_node)
        self.audio_source_id = audio_source_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            audio_source_node, 'out', self.mixer_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.audio_source_node)
        self.audio_source_id = None


state.StateBase.register_class(SampleTrack)
