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
  host_system.cpp
  host_system_lv2.cpp
  host_system_csound.cpp
  host_system_audio_file.cpp
)

add_library(noisicaa-host_system SHARED ${LIB_SRCS})
target_compile_options(noisicaa-host_system PRIVATE -fPIC -std=c++11 -Wall -Werror -pedantic -DHAVE_PTHREAD_SPIN_LOCK)
target_link_libraries(noisicaa-host_system PRIVATE noisicaa-core)
target_include_directories(noisicaa-host_system PUBLIC ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(noisicaa-host_system PRIVATE ${LIBLILV_LIBRARIES})
target_include_directories(noisicaa-host_system PRIVATE ${LIBCSOUND_INCLUDE_DIRS})
target_link_libraries(noisicaa-host_system PRIVATE ${LIBCSOUND_LIBRARIES})
target_include_directories(noisicaa-host_system PRIVATE ${LIBSNDFILE_INCLUDE_DIRS})
target_link_libraries(noisicaa-host_system PRIVATE ${LIBSNDFILE_LIBRARIES})
target_include_directories(noisicaa-host_system PRIVATE ${LIBAVUTIL_INCLUDE_DIRS})
target_link_libraries(noisicaa-host_system PRIVATE ${LIBAVUTIL_LIBRARIES})
target_include_directories(noisicaa-host_system PRIVATE ${LIBSWRESAMPLE_INCLUDE_DIRS})
target_link_libraries(noisicaa-host_system PRIVATE ${LIBSWRESAMPLE_LIBRARIES})

add_cython_module(host_system CXX)
target_link_libraries(${host_system.so} PRIVATE noisicaa-host_system)
