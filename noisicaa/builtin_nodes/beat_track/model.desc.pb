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
  name: "Beat"
  super_class: "noisicaa.music.model_base.ProjectChild"
  proto_ext_name: "beat"
  properties {
    name: "time"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.audioproc.MusicalDuration"
    proto_id: 1
  }
  properties {
    name: "velocity"
    type: UINT32
    proto_id: 2
  }
}

classes {
  name: "BeatMeasure"
  super_class: "noisicaa.music.base_track.Measure"
  proto_ext_name: "beat_measure"
  properties {
    name: "beats"
    type: OBJECT_LIST
    obj_type: "Beat"
    proto_id: 1
  }
}

classes {
  name: "BeatTrack"
  super_class: "noisicaa.music.base_track.MeasuredTrack"
  proto_ext_name: "beat_track"
  properties {
    name: "pitch"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.Pitch"
    proto_id: 1
  }
}
