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
  command_shell.py
  dock_widget.py
  editor_app.py
  editor_window.py
  flowlayout.py
  instrument_library.py
  instrument_library_test.py
  load_history.py
  misc.py
  model.py
  mute_button.py
  piano.py
  piano_test.py
  pipeline_graph_monitor.py
  pipeline_graph_view.py
  pipeline_perf_monitor.py
  project_properties_dock.py
  project_registry.py
  project_view.py
  project_view_test.py
  qled.py
  render_project_dialog.py
  render_project_dialog_test.py
  selection_set.py
  session_helpers.py
  settings.py
  stat_monitor.py
  svg_symbol_filetest.py
  svg_symbol.py
  svg_symbol_test.py
  tool_dock.py
  tools.py
  track_properties_dock.py
  tracks_dock.py
  tracks_dock_test.py
  ui_base.py
  ui_process.py
  uitest_utils.py
)

file(COPY testdata DESTINATION .)

add_subdirectory(track_items)
