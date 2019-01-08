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

from .model_base import (
    ObjectSpec,

    PropertyBase,
    Property, ListProperty,
    ProtoProperty,
    WrappedProtoProperty, WrappedProtoListProperty,
    ObjectProperty, ObjectReferenceProperty, ObjectListProperty,

    Mutation,
    ObjectChange,
    ObjectAdded,
    ObjectRemoved,
    PropertyChange,
    PropertyValueChange,
    PropertyListChange,
    PropertyListInsert, PropertyListDelete,

    AbstractPool, Pool,
)
from .key_signature import KeySignature
from .time_signature import TimeSignature
from .clef import Clef
from .pitch import Pitch, NOTE_TO_MIDI
from .pos2f import Pos2F
from .sizef import SizeF
from .color import Color
from .project import (
    ObjectBase,
    ProjectChild,
    AudioOutPipelineGraphNode,
    BasePipelineGraphNode,
    Measure,
    MeasureReference,
    MeasuredTrack,
    Metadata,
    PipelineGraphConnection,
    PipelineGraphControlValue,
    PipelineGraphNode,
    Project,
    Sample,
    Track,
)
from .model_base_pb2 import (
    ObjectTree,
)
from .project_pb2 import (
    ControlValue,
)
