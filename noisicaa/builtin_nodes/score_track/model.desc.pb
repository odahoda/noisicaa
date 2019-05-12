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
  name: "Note"
  super_class: "noisicaa.music.model_base.ProjectChild"
  proto_ext_name: "note"
  properties {
    name: "pitches"
    type: WRAPPED_PROTO_LIST
    wrapped_type: "noisicaa.value_types.Pitch"
    proto_id: 1;
  }
  properties {
    name: "base_duration"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.audioproc.MusicalDuration"
    default: "noisicaa.audioproc.MusicalDuration(1, 4)"
    proto_id: 2;
  }
  properties {
    name: "dots"
    type: UINT32
    default: "0"
    proto_id: 3;
  }
  properties {
    name: "tuplet"
    type: UINT32
    default: "0"
    proto_id: 4;
  }
}

classes {
  name: "ScoreMeasure"
  super_class: "noisicaa.music.base_track.Measure"
  proto_ext_name: "score_measure"
  properties {
    name: "clef"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.Clef"
    default: "noisicaa.value_types.Clef.Treble"
    proto_id: 1;
  }
  properties {
    name: "key_signature"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.KeySignature"
    default: "noisicaa.value_types.KeySignature('C major')"
    proto_id: 2;
  }
  properties {
    name: "notes"
    type: OBJECT_LIST
    obj_type: "Note"
    proto_id: 3;
  }
}

classes {
  name: "ScoreTrack"
  super_class: "noisicaa.music.base_track.MeasuredTrack"
  proto_ext_name: "score_track"
  properties {
    name: "transpose_octaves"
    type: INT32
    default: "0"
    proto_id: 1;
  }
}
