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
  sndfile_test.py
  sratom_test.py
)

add_cython_module(ladspa CXX)

add_cython_module(lilv CXX)
target_include_directories(${lilv.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(${lilv.so} PRIVATE ${LIBLILV_LIBRARIES})

add_cython_module(sndfile CXX)
target_include_directories(${sndfile.so} PRIVATE ${LIBSNDFILE_INCLUDE_DIRS})
target_link_libraries(${sndfile.so} PRIVATE ${LIBSNDFILE_LIBRARIES})

add_cython_module(sratom CXX)
target_include_directories(${sratom.so} PRIVATE ${LIBSRATOM_INCLUDE_DIRS})
target_link_libraries(${sratom.so} PRIVATE ${LIBSRATOM_LIBRARIES})

file(COPY testdata DESTINATION .)

add_subdirectory(lv2)
