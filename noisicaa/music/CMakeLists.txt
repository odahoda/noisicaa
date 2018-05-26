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

add_python_package(
  base_track.py
  base_track_test.py
  beat_track.py
  beat_track_test.py
  commands.py
  commands_test.py
  control_track.py
  control_track_test.py
  mutations.py
  pipeline_graph.py
  pipeline_graph_test.py
  player.py
  player_integration_test.py
  player_test.py
  pmodel.py
  pmodel_test.py
  project_client.py
  project_client_test.py
  project_integration_test.py
  project_process.py
  project.py
  project_test.py
  render.py
  render_test.py
  rms.pyi
  sample_track.py
  sample_track_test.py
  score_track.py
  score_track_test.py
  property_track.py
  property_track_test.py
  track_group.py
  track_group_test.py
)

add_cython_module(rms CXX)

py_proto(render_settings.proto)
py_proto(mutations.proto)
py_proto(commands.proto)
