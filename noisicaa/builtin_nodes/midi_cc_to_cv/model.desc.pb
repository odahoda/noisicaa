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

template: "noisicaa/builtin_nodes/model.tmpl.py"

classes {
  name: "MidiCCtoCVChannel"
  super_class: "noisicaa.music.model.ProjectChild"
  proto_ext_name: "midi_cc_to_cv_channel"
  properties {
    name: "type"
    type: PROTO_ENUM
    proto_id: 1
    proto_enum_name: "Type"
    proto_enum_fields {
      name: "CONTROLLER"
      value: 1
    }
  }
  properties {
    name: "midi_channel"
    type: UINT32
    default: "0"
    proto_id: 2
  }
  properties {
    name: "midi_controller"
    type: UINT32
    default: "0"
    proto_id: 3
  }
  properties {
    name: "min_value"
    type: FLOAT
    default: "0.0"
    proto_id: 4
  }
  properties {
    name: "max_value"
    type: FLOAT
    default: "1.0"
    proto_id: 5
  }
  properties {
    name: "log_scale"
    type: BOOL
    default: "False"
    proto_id: 6
  }
}

classes {
  name: "MidiCCtoCV"
  super_class: "noisicaa.music.graph.BaseNode"
  proto_ext_name: "midi_cc_to_cv"
  properties {
    name: "channels"
    type: OBJECT_LIST
    obj_type: "MidiCCtoCVChannel"
    proto_id: 1
  }
}
