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
  name: "TransferFunction"
  super_class: "ObjectBase"
  proto_ext_name: "transfer_function"
  properties {
    name: "input_min"
    type: FLOAT
    proto_id: 1
  }
  properties {
    name: "input_max"
    type: FLOAT
    proto_id: 2
  }
  properties {
    name: "output_min"
    type: FLOAT
    proto_id: 3
  }
  properties {
    name: "output_max"
    type: FLOAT
    proto_id: 4
  }
  properties {
    name: "type"
    type: PROTO_ENUM
    proto_id: 5
    proto_enum_name: "Type"
    proto_enum_fields {
      name: "FIXED"
      value: 1
    }
    proto_enum_fields {
      name: "LINEAR"
      value: 2
    }
    proto_enum_fields {
      name: "GAMMA"
      value: 3
    }
  }
  properties {
    name: "fixed_value"
    type: FLOAT
    proto_id: 6
  }
  properties {
    name: "linear_left_value"
    type: FLOAT
    proto_id: 7
  }
  properties {
    name: "linear_right_value"
    type: FLOAT
    proto_id: 8
  }
  properties {
    name: "gamma_value"
    type: FLOAT
    proto_id: 9
  }
}

classes {
  name: "BaseNode"
  is_abstract: true
  super_class: "ObjectBase"
  proto_ext_name: "base_node"
  properties {
    name: "name"
    type: STRING
    proto_id: 1
  }
  properties {
    name: "graph_pos"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.Pos2F"
    proto_id: 2
  }
  properties {
    name: "graph_size"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.SizeF"
    proto_id: 5
  }
  properties {
    name: "graph_color"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.Color"
    proto_id: 6
    default: "noisicaa.value_types.Color(0.8, 0.8, 0.8, 1.0)"
  }
  properties {
    name: "control_values"
    type: WRAPPED_PROTO_LIST
    wrapped_type: "noisicaa.value_types.ControlValue"
    proto_id: 3
  }
  properties {
    name: "plugin_state"
    type: PROTO
    proto_type: "noisicaa.audioproc.PluginState"
    proto_id: 4
    allow_none: true
  }
  properties {
    name: "port_properties"
    type: WRAPPED_PROTO_LIST
    wrapped_type: "noisicaa.value_types.NodePortProperties"
    proto_id: 7
  }
}

classes {
  name: "Port"
  is_abstract: true
  super_class: "ObjectBase"
  proto_ext_name: "port"
  properties {
    name: "name"
    type: STRING
    proto_id: 1
  }
  properties {
    name: "display_name"
    type: STRING
    proto_id: 2
    allow_none: true
  }
  properties {
    name: "type"
    type: INT32  # TODO: PortDescription.Type
    proto_id: 3
  }
  properties {
    name: "direction"
    type: INT32  # TODO: PortDescription.Direction
    proto_id: 4
  }
}

classes {
  name: "Node"
  super_class: "ObjectBase"
  proto_ext_name: "node"
  properties {
    name: "node_uri"
    type: STRING
    proto_id: 1
  }
}

classes {
  name: "SystemOutNode"
  super_class: "ObjectBase"
  proto_ext_name: "system_out_node"
}

classes {
  name: "NodeConnection"
  super_class: "ObjectBase"
  proto_ext_name: "node_connection"
  properties {
    name: "source_node"
    type: OBJECT_REF
    obj_type: "BaseNode"
    obj_mod: "noisicaa.music.graph"
    proto_id: 1
  }
  properties {
    name: "source_port"
    type: STRING
    proto_id: 2
  }
  properties {
    name: "dest_node"
    type: OBJECT_REF
    obj_type: "BaseNode"
    obj_mod: "noisicaa.music.graph"
    proto_id: 3
  }
  properties {
    name: "dest_port"
    type: STRING
    proto_id: 4
  }
  properties {
    name: "type"
    type: INT32  # TODO: PortDescription.Type
    allow_none: true
    proto_id: 5
  }
}

classes {
  name: "Track"
  is_abstract: true
  super_class: "ObjectBase"
  proto_ext_name: "track"
  properties {
    name: "visible"
    type: BOOL
    proto_id: 1
    default: "True"
  }
  properties {
    name: "list_position"
    type: UINT32
    proto_id: 2
    default: "0"
  }
}

classes {
  name: "Measure"
  is_abstract: true
  super_class: "ObjectBase"
  proto_ext_name: "measure"
  properties {
    name: "time_signature"
    type: WRAPPED_PROTO
    wrapped_type: "noisicaa.value_types.TimeSignature"
    proto_id: 1
    default: "noisicaa.value_types.TimeSignature(4, 4)"
  }
}

classes {
  name: "MeasureReference"
  super_class: "ObjectBase"
  proto_ext_name: "measure_reference"
  properties {
    name: "measure"
    type: OBJECT_REF
    obj_type: "Measure"
    obj_mod: "noisicaa.music.base_track"
    proto_id: 1
  }
}

classes {
  name: "MeasuredTrack"
  is_abstract: true
  super_class: "ObjectBase"
  proto_ext_name: "measured_track"
  properties {
    name: "measure_list"
    type: OBJECT_LIST
    obj_type: "MeasureReference"
    obj_mod: "noisicaa.music.base_track"
    proto_id: 1
  }
  properties {
    name: "measure_heap"
    type: OBJECT_LIST
    obj_type: "Measure"
    obj_mod: "noisicaa.music.base_track"
    proto_id: 2
  }
}

classes {
  name: "Sample"
  super_class: "ObjectBase"
  proto_ext_name: "sample"
  properties {
    name: "path"
    type: STRING
    proto_id: 1
  }
}

classes {
  name: "Metadata"
  super_class: "ObjectBase"
  proto_ext_name: "metadata"
  properties {
    name: "author"
    type: STRING
    proto_id: 1
    allow_none: true
  }
  properties {
    name: "license"
    type: STRING
    proto_id: 2
    allow_none: true
  }
  properties {
    name: "copyright"
    type: STRING
    proto_id: 3
    allow_none: true
  }
  properties {
    name: "created"
    type: UINT32
    proto_id: 4
    allow_none: true
  }
}

classes {
  name: "Project"
  super_class: "ObjectBase"
  proto_ext_name: "project"
  properties {
    name: "metadata"
    type: OBJECT
    obj_type: "Metadata"
    obj_mod: "noisicaa.music.metadata"
    proto_id: 1
  }
  properties {
    name: "bpm"
    type: UINT32
    proto_id: 2
    default: "120"
  }
  properties {
    name: "nodes"
    type: OBJECT_LIST
    obj_type: "BaseNode"
    obj_mod: "noisicaa.music.graph"
    proto_id: 3
  }
  properties {
    name: "node_connections"
    type: OBJECT_LIST
    obj_type: "NodeConnection"
    obj_mod: "noisicaa.music.graph"
    proto_id: 4
  }
  properties {
    name: "samples"
    type: OBJECT_LIST
    obj_type: "Sample"
    obj_mod: "noisicaa.music.samples"
    proto_id: 5
  }
}
