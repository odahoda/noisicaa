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
  auto_cleanup_mixin.py
  backend_manager.py
  backend_manager_test.py
  callbacks.py
  callbacks_test.py
  fileutil.py
  fileutil_test.py
  ipc.py
  ipc_test.py
  logging.pyi
  perf_stats_test.py
  process_manager.py
  process_manager_test.py
  recordfile.py
  recordfile_test.py
  stacktrace.pyi
  stats_test.py
  storage.py
  storage_test.py
  threads.py
  threads_test.py
  typing_extra.py
)

add_cython_module(logging_test CXX)
target_link_libraries(${logging_test.so} PRIVATE noisicaa-core)

py_proto(empty_message.proto)
py_proto(storage.proto)
py_proto(ipc.proto)
py_proto(process_manager.proto)
py_proto(ipc_test.proto)
py_proto(session_data.proto)

set(LIB_SRCS
  logging.cpp
  perf_stats.cpp
  refcount.cpp
  status.cpp
  stacktrace.cpp
)

add_library(noisicaa-core SHARED ${LIB_SRCS})
target_link_libraries(noisicaa-core PRIVATE pthread)
target_include_directories(noisicaa-core PRIVATE ${LIBUNWIND_INCLUDE_DIRS})
target_link_libraries(noisicaa-core PRIVATE ${LIBUNWIND_LIBRARIES})

add_cython_module(perf_stats CXX)
target_link_libraries(${perf_stats.so} PRIVATE noisicaa-core)

add_cython_module(logging CXX)
target_link_libraries(${logging.so} PRIVATE noisicaa-core)

add_cython_module(status CXX)
target_link_libraries(${status.so} PRIVATE noisicaa-core)

add_cython_module(stacktrace CXX)
target_link_libraries(${stacktrace.so} PRIVATE noisicaa-core)

add_subdirectory(stats)
