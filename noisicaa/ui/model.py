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

import logging

from noisicaa import audioproc
from noisicaa.music import model
from noisicaa.music import project_client

logger = logging.getLogger(__name__)

# TODO: almost duplicate code. This should be in music/model.py, but only after
# the UI code has been changed to call the listeners directly with PropertyChange
# instances.
class MeasuredTrackMixin(object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__listeners = {}

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.listeners.add('measure_list', self.__measure_list_changed)

    def __measure_list_changed(self, action, index, value):
        if action == 'insert':
            self.__add_measure(value)
        elif action == 'delete':
            self.__remove_measure(value)
        else:
            raise TypeError("Unsupported change type %s" % type(action))

    def __add_measure(self, mref):
        self.__listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda *_: self.__measure_id_changed(mref))
        self.listeners.call('duration_changed')

    def __remove_measure(self, mref):
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.listeners.call('duration_changed')

    def __measure_id_changed(self, mref):
        self.listeners.call('duration_changed')


# TODO: almost duplicate code. This should be in music/model.py, but only after
# the UI code has been changed to call the listeners directly with PropertyChange
# instances.
class TrackGroupMixin(object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__listeners = {}
        for track in self.tracks:
            self.__add_track(track)
        self.listeners.add('tracks', self.__tracks_changed)

    def __tracks_changed(self, action, index, value):
        if action == 'insert':
            self.__add_track(value)
        elif action == 'delete':
            self.__remove_track(value)
        else:
            raise TypeError("Unsupported change type %s" % action)

    def __add_track(self, track):
        self.__listeners['%s:duration_changed' % track.id] = track.listeners.add(
            'duration_changed', lambda: self.listeners.call('duration_changed'))
        self.listeners.call('duration_changed')

    def __remove_track(self, track):
        self.__listeners.pop('%s:duration_changed' % track.id).remove()
        self.listeners.call('duration_changed')


class MeasureReference(model.MeasureReference, project_client.ObjectProxy): pass

class Note(model.Note, project_client.ObjectProxy):
    def property_changed(self, changes):
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('notes-changed')

class ScoreMeasure(model.ScoreMeasure, project_client.ObjectProxy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.listeners.add(
            'notes', lambda *args: self.listeners.call('notes-changed'))

class ScoreTrack(MeasuredTrackMixin, model.ScoreTrack, project_client.ObjectProxy): pass

class Beat(model.Beat, project_client.ObjectProxy):
    def property_changed(self, changes):
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('beats-changed')

class BeatMeasure(model.BeatMeasure, project_client.ObjectProxy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.listeners.add(
            'beats', lambda *args: self.listeners.call('beats-changed'))

class BeatTrack(MeasuredTrackMixin, model.BeatTrack, project_client.ObjectProxy): pass
class TrackGroup(TrackGroupMixin, model.TrackGroup, project_client.ObjectProxy): pass
class MasterTrackGroup(TrackGroupMixin, model.MasterTrackGroup, project_client.ObjectProxy): pass
class ControlPoint(model.ControlPoint, project_client.ObjectProxy): pass
class ControlTrack(model.ControlTrack, project_client.ObjectProxy): pass
class SampleRef(model.SampleRef, project_client.ObjectProxy): pass
class SampleTrack(model.SampleTrack, project_client.ObjectProxy): pass
class PropertyMeasure(model.PropertyMeasure, project_client.ObjectProxy): pass
class PropertyTrack(model.PropertyTrack, project_client.ObjectProxy): pass
class PipelineGraphNodeParameterValue(model.PipelineGraphNodeParameterValue, project_client.ObjectProxy): pass
class PipelineGraphControlValue(model.PipelineGraphControlValue, project_client.ObjectProxy): pass
class PipelineGraphPortPropertyValue(model.PipelineGraphPortPropertyValue, project_client.ObjectProxy): pass
class PipelineGraphNode(model.PipelineGraphNode, project_client.ObjectProxy): pass
class AudioOutPipelineGraphNode(model.AudioOutPipelineGraphNode, project_client.ObjectProxy): pass
class TrackMixerPipelineGraphNode(model.TrackMixerPipelineGraphNode, project_client.ObjectProxy): pass
class CVGeneratorPipelineGraphNode(model.CVGeneratorPipelineGraphNode, project_client.ObjectProxy): pass
class SampleScriptPipelineGraphNode(model.SampleScriptPipelineGraphNode, project_client.ObjectProxy): pass
class PianoRollPipelineGraphNode(model.PianoRollPipelineGraphNode, project_client.ObjectProxy): pass
class InstrumentPipelineGraphNode(model.InstrumentPipelineGraphNode, project_client.ObjectProxy): pass
class PipelineGraphConnection(model.PipelineGraphConnection, project_client.ObjectProxy): pass
class Sample(model.Sample, project_client.ObjectProxy): pass
class Metadata(model.Metadata, project_client.ObjectProxy): pass
class Project(model.Project, project_client.ObjectProxy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_root = True

        self.__node_db = None
        self.__obj_map = None

        self.__duration = audioproc.MusicalDuration()
        self.__master_group_listener = None
        self.listeners.add('master_group', self.__on_master_group_changed)

        self.__time_mapper = audioproc.TimeMapper()
        self.__time_mapper.setup(self)

    @property
    def duration(self):
        return self.__duration

    def __update_duration(self):
        if self.__obj_map is None or self.master_group is None:
            return

        new_duration = self.master_group.duration
        if new_duration != self.__duration:
            old_duration = self.__duration
            self.__duration = new_duration
            self.listeners.call('duration', old_duration, new_duration)

    def __on_master_group_changed(self, old_value, new_value):
        if self.__master_group_listener is not None:
            self.__master_group_listener.remove()
            self.__master_group_listener = None

        if self.master_group is not None:
            self.__master_group_listener = self.master_group.listeners.add(
                'duration_changed', self.__update_duration)
            self.__update_duration()

    @property
    def time_mapper(self):
        return self.__time_mapper

    def init(self, node_db, obj_map):
        self.__node_db = node_db
        self.__obj_map = obj_map

        self.__update_duration()

    def get_node_description(self, uri):
        return self.__node_db.get_node_description(uri)

    def get_object(self, obj_id):
        assert self.__obj_map is not None
        return self.__obj_map[obj_id]

    def add_object(self, obj):
        pass

    def remove_object(self, obj):
        pass


cls_map = {
    'MeasureReference': MeasureReference,
    'Note': Note,
    'ScoreMeasure': ScoreMeasure,
    'ScoreTrack': ScoreTrack,
    'Beat': Beat,
    'BeatMeasure': BeatMeasure,
    'BeatTrack': BeatTrack,
    'TrackGroup': TrackGroup,
    'MasterTrackGroup': MasterTrackGroup,
    'ControlPoint': ControlPoint,
    'ControlTrack': ControlTrack,
    'SampleRef': SampleRef,
    'SampleTrack': SampleTrack,
    'PropertyMeasure': PropertyMeasure,
    'PropertyTrack': PropertyTrack,
    'PipelineGraphNodeParameterValue': PipelineGraphNodeParameterValue,
    'PipelineGraphControlValue': PipelineGraphControlValue,
    'PipelineGraphPortPropertyValue': PipelineGraphPortPropertyValue,
    'PipelineGraphNode': PipelineGraphNode,
    'AudioOutPipelineGraphNode': AudioOutPipelineGraphNode,
    'TrackMixerPipelineGraphNode': TrackMixerPipelineGraphNode,
    'CVGeneratorPipelineGraphNode': CVGeneratorPipelineGraphNode,
    'SampleScriptPipelineGraphNode': SampleScriptPipelineGraphNode,
    'PianoRollPipelineGraphNode': PianoRollPipelineGraphNode,
    'InstrumentPipelineGraphNode': InstrumentPipelineGraphNode,
    'PipelineGraphConnection': PipelineGraphConnection,
    'Sample': Sample,
    'Metadata': Metadata,
    'Project': Project,
}
