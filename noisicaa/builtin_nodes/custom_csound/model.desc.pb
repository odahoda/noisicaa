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
  name: "CustomCSoundPort"
  super_class: "noisicaa.music.graph.Port"
  proto_ext_name: "custom_csound_port"
  properties {
    name: "csound_name"
    type: STRING
    allow_none: true
    proto_id: 1
  }
}

classes {
  name: "CustomCSound"
  super_class: "noisicaa.music.graph.BaseNode"
  proto_ext_name: "custom_csound"
  properties {
    name: "orchestra"
    type: STRING
    allow_none: true
    proto_id: 1
  }
  properties {
    name: "score"
    type: STRING
    allow_none: true
    proto_id: 2
  }
  properties {
    name: "ports"
    type: OBJECT_LIST
    obj_type: "CustomCSoundPort"
    proto_id: 3
  }
}
