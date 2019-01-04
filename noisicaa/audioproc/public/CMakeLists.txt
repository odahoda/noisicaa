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

add_python_package()

set(LIB_SRCS
  engine_notification.pb.cc
  instrument_spec.pb.cc
  musical_time.cpp
  musical_time.pb.cc
  player_state.pb.cc
  plugin_state.pb.cc
  processor_message.pb.cc
  time_mapper.cpp
)

set(TEST_SRCS
  musical_time_test.pyx
  time_mapper_test.pyx
)

cpp_proto(instrument_spec.proto)
py_proto(instrument_spec.proto)
cpp_proto(musical_time.proto)
py_proto(musical_time.proto)
cpp_proto(player_state.proto)
py_proto(player_state.proto)
cpp_proto(plugin_state.proto)
py_proto(plugin_state.proto)
cpp_proto(processor_message.proto)
py_proto(processor_message.proto)
cpp_proto(engine_notification.proto)
py_proto(engine_notification.proto)

add_library(noisicaa-audioproc-public SHARED ${LIB_SRCS})
target_compile_options(noisicaa-audioproc-public PRIVATE -fPIC -std=c++11 -Wall -Werror -pedantic -DHAVE_PTHREAD_SPIN_LOCK)
target_link_libraries(noisicaa-audioproc-public PRIVATE noisicaa-core)
target_include_directories(noisicaa-audioproc-public PRIVATE ${LIBPROTOBUF_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-public PRIVATE ${LIBPROTOBUF_LIBRARIES})

add_cython_module(musical_time CXX)
target_link_libraries(${musical_time.so} PRIVATE noisicaa-audioproc-public)

add_cython_module(time_mapper CXX)
target_link_libraries(${time_mapper.so} PRIVATE noisicaa-audioproc-public)

foreach(TEST_SRC ${TEST_SRCS})
  string(REGEX REPLACE "\.pyx$" "" TEST_MOD ${TEST_SRC})
  add_cython_module(${TEST_MOD} CXX)
  target_link_libraries(${${TEST_MOD}.so} PRIVATE noisicaa-audioproc-public)
  target_include_directories(${${TEST_MOD}.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
  target_link_libraries(${${TEST_MOD}.so} PRIVATE ${LIBLILV_LIBRARIES})
endforeach(TEST_SRC)
