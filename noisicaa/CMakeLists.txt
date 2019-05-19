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
  constants.py
  debug_console.py
  editor_main.py
  exceptions.py
  logging.py
  pdb.py
  runtime_settings.py
  utils.py
)

py_proto(editor_main.proto)

add_subdirectory(audioproc)
add_subdirectory(bindings)
add_subdirectory(core)
add_subdirectory(host_system)
add_subdirectory(instr)
add_subdirectory(instrument_db)
add_subdirectory(lv2)
add_subdirectory(value_types)
add_subdirectory(music)
add_subdirectory(node_db)
add_subdirectory(ui)
add_subdirectory(builtin_nodes)
