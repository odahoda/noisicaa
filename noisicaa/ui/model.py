#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa.music import model
from noisicaa.music import project_client
from noisicaa.music import node_db

logger = logging.getLogger(__name__)

class SoundFontInstrument(
        model.SoundFontInstrument, project_client.ObjectProxy): pass
class Measure(model.Measure, project_client.ObjectProxy): pass
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
class TrackGroup(model.TrackGroup, project_client.ObjectProxy): pass
class MasterTrackGroup(model.MasterTrackGroup, project_client.ObjectProxy): pass
class SheetPropertyMeasure(model.SheetPropertyMeasure, project_client.ObjectProxy): pass
class SheetPropertyTrack(model.SheetPropertyTrack, project_client.ObjectProxy): pass
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

        self.node_db = node_db.NodeDB()
        self.node_db.setup()

    def get_node_description(self, uri):
        return self.node_db.get_node_description(uri)


cls_map = {
    'SoundFontInstrument': SoundFontInstrument,
    'Measure': Measure,
    'Track': Track,
    'Note': Note,
    'ScoreMeasure': ScoreMeasure,
    'ScoreTrack': ScoreTrack,
    'TrackGroup': TrackGroup,
    'MasterTrackGroup': MasterTrackGroup,
    'SheetPropertyMeasure': SheetPropertyMeasure,
    'SheetPropertyTrack': SheetPropertyTrack,
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
