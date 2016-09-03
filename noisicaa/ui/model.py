#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa import node_db
from noisicaa.music import model
from noisicaa.music import project_client

logger = logging.getLogger(__name__)

class SoundFontInstrument(
        model.SoundFontInstrument, project_client.ObjectProxy): pass
class Measure(model.Measure, project_client.ObjectProxy): pass
class MeasureReference(model.MeasureReference, project_client.ObjectProxy): pass
class Track(model.Track, project_client.ObjectProxy): pass

class Note(model.Note, project_client.ObjectProxy):
    def property_changed(self, changes):
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('notes-changed')

class ScoreMeasure(model.ScoreMeasure, project_client.ObjectProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listeners.add(
            'notes', lambda *args: self.listeners.call('notes-changed'))

class ScoreTrack(model.ScoreTrack, project_client.ObjectProxy): pass

class Beat(model.Beat, project_client.ObjectProxy):
    def property_changed(self, changes):
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('beats-changed')

class BeatMeasure(model.BeatMeasure, project_client.ObjectProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listeners.add(
            'beats', lambda *args: self.listeners.call('beats-changed'))

class BeatTrack(model.BeatTrack, project_client.ObjectProxy): pass
class TrackGroup(model.TrackGroup, project_client.ObjectProxy): pass
class MasterTrackGroup(model.MasterTrackGroup, project_client.ObjectProxy): pass
class SheetPropertyMeasure(model.SheetPropertyMeasure, project_client.ObjectProxy): pass
class SheetPropertyTrack(model.SheetPropertyTrack, project_client.ObjectProxy): pass
class PipelineGraphNodeParameterValue(model.PipelineGraphNodeParameterValue, project_client.ObjectProxy): pass
class PipelineGraphPortPropertyValue(model.PipelineGraphPortPropertyValue, project_client.ObjectProxy): pass
class PipelineGraphNode(model.PipelineGraphNode, project_client.ObjectProxy): pass
class AudioOutPipelineGraphNode(model.AudioOutPipelineGraphNode, project_client.ObjectProxy): pass
class TrackMixerPipelineGraphNode(model.TrackMixerPipelineGraphNode, project_client.ObjectProxy): pass
class EventSourcePipelineGraphNode(model.EventSourcePipelineGraphNode, project_client.ObjectProxy): pass
class InstrumentPipelineGraphNode(model.InstrumentPipelineGraphNode, project_client.ObjectProxy): pass
class PipelineGraphConnection(model.PipelineGraphConnection, project_client.ObjectProxy): pass
class Sheet(model.Sheet, project_client.ObjectProxy): pass
class Metadata(model.Metadata, project_client.ObjectProxy): pass
class Project(model.Project, project_client.ObjectProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_root = True

        self.__node_db = None
        self.__obj_map = None

    def init(self, node_db, obj_map):
        self.__node_db = node_db
        self.__obj_map = obj_map

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
    'SoundFontInstrument': SoundFontInstrument,
    'Measure': Measure,
    'MeasureReference': MeasureReference,
    'Track': Track,
    'Note': Note,
    'ScoreMeasure': ScoreMeasure,
    'ScoreTrack': ScoreTrack,
    'Beat': Beat,
    'BeatMeasure': BeatMeasure,
    'BeatTrack': BeatTrack,
    'TrackGroup': TrackGroup,
    'MasterTrackGroup': MasterTrackGroup,
    'SheetPropertyMeasure': SheetPropertyMeasure,
    'SheetPropertyTrack': SheetPropertyTrack,
    'PipelineGraphNodeParameterValue': PipelineGraphNodeParameterValue,
    'PipelineGraphPortPropertyValue': PipelineGraphPortPropertyValue,
    'PipelineGraphNode': PipelineGraphNode,
    'AudioOutPipelineGraphNode': AudioOutPipelineGraphNode,
    'TrackMixerPipelineGraphNode': TrackMixerPipelineGraphNode,
    'EventSourcePipelineGraphNode': EventSourcePipelineGraphNode,
    'InstrumentPipelineGraphNode': InstrumentPipelineGraphNode,
    'PipelineGraphConnection': PipelineGraphConnection,
    'Sheet': Sheet,
    'Metadata': Metadata,
    'Project': Project,
}
