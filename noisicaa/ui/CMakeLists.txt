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
  audio_thread_profiler.py
  control_value_connector.py
  control_value_dial.py
  device_list.py
  dynamic_layout.py
  editor_app.py
  editor_window.py
  flowlayout.py
  gain_slider.py
  instrument_library.py
  instrument_library_test.py
  load_history.py
  misc.py
  mute_button.py
  piano.py
  piano_test.py
  pipeline_perf_monitor.py
  player_state.py
  project_registry.py
  project_view.py
  project_view_test.py
  qled.py
  qprogressindicator.py
  render_dialog.py
  render_dialog_test.py
  selection_set.py
  session_helpers.py
  settings.py
  slots.py
  stat_monitor.py
  svg_symbol_filetest.py
  svg_symbol.py
  svg_symbol_test.py
  ui_base.py
  ui_process.py
  vumeter.py
)

add_subdirectory(track_list)
add_subdirectory(pipeline_graph)
