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
  client.py
  client_test.py
  presets.py
  presets_test.py
  process.py
  utils.py
)

set(LIB_SRCS
  node_description.pb.cc
)

py_proto(node_db.proto)
cpp_proto(node_description.proto)
py_proto(node_description.proto)

add_library(noisicaa-node_db SHARED ${LIB_SRCS})
target_include_directories(noisicaa-node_db PRIVATE ${LIBPROTOBUF_INCLUDE_DIRS})
target_link_libraries(noisicaa-node_db PRIVATE ${LIBPROTOBUF_LIBRARIES})

add_subdirectory(private)
