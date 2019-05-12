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

add_python_package(
  base_track.py
  base_track_test.py
  graph.py
  graph_test.py
  metadata.py
  model_base.py
  model_base_test.py
  mutations.py
  node_connector.py
  player.py
  player_integration_test.py
  player_test.py
  project.py
  project_client.py
  project_client_test.py
  project_integration_test.py
  project_test.py
  render.py
  render_test.py
  rms.pyi
  samples.py
  session_value_store.py
  writer_client.py
  writer_client_test.py
  writer_process.py
)

add_cython_module(rms CXX)

build_model(model.desc.pb _model.py noisicaa/music/model.py)

py_proto(model.proto)
add_dependencies(noisicaa.music.model.proto model-noisicaa.music)
py_proto(project.proto)
add_dependencies(noisicaa.music.project.proto noisicaa.music.model.proto)
py_proto(model_base.proto)
py_proto(model_base_test.proto)
py_proto(writer_process.proto)
py_proto(render.proto)
py_proto(mutations.proto)
add_dependencies(noisicaa.music.mutations.proto noisicaa.music.model.proto)
