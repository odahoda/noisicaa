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
  name: "StepSequencerStep"
  super_class: "noisicaa.music.model_base.ProjectChild"
  proto_ext_name: "step_sequencer_step"
  properties {
    name: "enabled"
    type: BOOL
    default: "False"
    proto_id: 1
  }
  properties {
    name: "value"
    type: FLOAT
    default: "0.0"
    proto_id: 2
  }
}

classes {
  name: "StepSequencerChannel"
  super_class: "noisicaa.music.model_base.ProjectChild"
  proto_ext_name: "step_sequencer_channel"
  properties {
    name: "type"
    type: PROTO_ENUM
    proto_id: 1
    proto_enum_name: "Type"
    proto_enum_fields {
      name: "VALUE"
      value: 1
    }
    proto_enum_fields {
      name: "GATE"
      value: 2
    }
    proto_enum_fields {
      name: "TRIGGER"
      value: 3
    }
  }
  properties {
    name: "steps"
    type: OBJECT_LIST
    obj_type: "StepSequencerStep"
    proto_id: 2
  }
  properties {
    name: "min_value"
    type: FLOAT
    default: "0.0"
    proto_id: 3
  }
  properties {
    name: "max_value"
    type: FLOAT
    default: "1.0"
    proto_id: 4
  }
  properties {
    name: "log_scale"
    type: BOOL
    default: "False"
    proto_id: 5
  }
}

classes {
  name: "StepSequencer"
  super_class: "noisicaa.music.graph.BaseNode"
  proto_ext_name: "step_sequencer"
  properties {
    name: "channels"
    type: OBJECT_LIST
    obj_type: "StepSequencerChannel"
    proto_id: 1
  }
  properties {
    name: "time_synched"
    type: BOOL
    default: "False"
    proto_id: 2
  }
  properties {
    name: "num_steps"
    type: UINT32
    default: "8"
    proto_id: 3
  }
}
