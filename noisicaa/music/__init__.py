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

from .project_client import (
    ProjectClient,

    ObjectBase,
    ProjectChild,
    Track,
    Measure,
    MeasureReference,
    MeasuredTrack,
    Note,
    TrackGroup,
    MasterTrackGroup,
    ScoreMeasure,
    ScoreTrack,
    Beat,
    BeatMeasure,
    BeatTrack,
    PropertyMeasure,
    PropertyTrack,
    ControlPoint,
    ControlTrack,
    SampleRef,
    SampleTrack,
    PipelineGraphControlValue,
    BasePipelineGraphNode,
    PipelineGraphNode,
    AudioOutPipelineGraphNode,
    TrackMixerPipelineGraphNode,
    PianoRollPipelineGraphNode,
    CVGeneratorPipelineGraphNode,
    SampleScriptPipelineGraphNode,
    InstrumentPipelineGraphNode,
    PipelineGraphConnection,
    Sample,
    Metadata,
    Project,
)
from .render_settings_pb2 import (
    RenderSettings,
)
from .mutations_pb2 import (
    MutationList,
)
from .commands_pb2 import (
    Command,

    UpdateProjectProperties,
    AddTrack,
    RemoveTrack,
    InsertMeasure,
    RemoveMeasure,
    MoveTrack,
    ReparentTrack,
    UpdateTrackProperties,
    SetNumMeasures,
    ClearMeasures,
    PasteMeasures,
    AddPipelineGraphNode,
    RemovePipelineGraphNode,
    AddPipelineGraphConnection,
    RemovePipelineGraphConnection,
    SetTimeSignature,
    SetInstrument,
    ChangeNote,
    InsertNote,
    DeleteNote,
    AddPitch,
    RemovePitch,
    SetClef,
    SetKeySignature,
    SetAccidental,
    TransposeNotes,
    AddControlPoint,
    RemoveControlPoint,
    MoveControlPoint,
    AddSample,
    RemoveSample,
    MoveSample,
    RenderSample,
    SetBeatTrackInstrument,
    SetBeatTrackPitch,
    SetBeatVelocity,
    AddBeat,
    RemoveBeat,
    SetPipelineGraphNodePos,
    SetPipelineGraphControlValue,
    SetPipelineGraphPluginState,
    PipelineGraphNodeToPreset,
    PipelineGraphNodeFromPreset,
)
