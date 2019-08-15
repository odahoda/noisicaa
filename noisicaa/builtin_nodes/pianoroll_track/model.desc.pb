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

classes {
  name: "PianoRollSegment"
  super_class: "noisicaa.music.model_base.ProjectChild"
  proto_ext_name: "pianoroll_segment"
  properties {
    name: "duration"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.audioproc.MusicalDuration"
    proto_id: 1
  }
  properties {
    name: "events"
    type: WRAPPED_PROTO_LIST
    wrapped_type: "noisicaa.value_types.MidiEvent"
    proto_id: 2
  }
}

classes {
  name: "PianoRollSegmentRef"
  super_class: "noisicaa.music.model_base.ProjectChild"
  proto_ext_name: "pianoroll_segment_ref"
  properties {
    name: "time"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.audioproc.MusicalTime"
    proto_id: 1
  }
  properties {
    name: "segment"
    type: OBJECT_REF
    obj_type: "PianoRollSegment"
    proto_id: 2
  }
}

classes {
  name: "PianoRollTrack"
  super_class: "noisicaa.music.base_track.Track"
  proto_ext_name: "pianoroll_track"
  properties {
    name: "segments"
    type: OBJECT_LIST
    obj_type: "PianoRollSegmentRef"
    proto_id: 1
  }
  properties {
    name: "segment_heap"
    type: OBJECT_LIST
    obj_type: "PianoRollSegment"
    proto_id: 2
  }
}
