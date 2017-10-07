# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
  audio_stream_test.py
  compiler.py
  compiler_test.py
  engine_perftest.py
  engine_test.py
  graph.py
)

set(LIB_SRCS
  audio_stream.cpp
  backend.cpp
  backend_ipc.cpp
  backend_null.cpp
  backend_portaudio.cpp
  buffers.cpp
  control_value.cpp
  host_data.cpp
  host_system_lv2.cpp
  host_system_csound.cpp
  misc.cpp
  message_queue.cpp
  opcodes.cpp
  processor_spec.cpp
  processor.cpp
  processor_null.cpp
  processor_ladspa.cpp
  processor_lv2.cpp
  processor_csound_base.cpp
  processor_csound.cpp
  processor_custom_csound.cpp
  processor_ipc.cpp
  processor_fluidsynth.cpp
  processor_sample_player.cpp
  processor_sound_file.cpp
  processor_track_mixer.cpp
  spec.cpp
  vm.cpp
)

set(TEST_SRCS
  backend_test.pyx
  backend_ipc_test.pyx
  buffers_test.pyx
  opcodes_test.pyx
  processor_test.pyx
  processor_ladspa_test.pyx
  processor_lv2_test.pyx
  processor_csound_test.pyx
  processor_ipc_test.pyx
  processor_fluidsynth_test.pyx
  processor_sample_player_test.pyx
  processor_sound_file_test.pyx
  processor_track_mixer_test.pyx
  spec_test.pyx
  vm_test.pyx
)

add_cpp_capnp(block_data.capnp)
add_py_capnp(block_data.capnp)

add_library(noisicaa-audioproc-vm SHARED ${LIB_SRCS} block_data.capnp.c++)
target_compile_options(noisicaa-audioproc-vm PRIVATE -fPIC -std=c++11 -Wall -Werror -pedantic -DHAVE_PTHREAD_SPIN_LOCK)
target_link_libraries(noisicaa-audioproc-vm PRIVATE noisicaa-core)
target_link_libraries(noisicaa-audioproc-vm PRIVATE noisicaa-lv2)
target_link_libraries(noisicaa-audioproc-vm PRIVATE capnp)
target_link_libraries(noisicaa-audioproc-vm PRIVATE pthread)
target_link_libraries(noisicaa-audioproc-vm PRIVATE portaudio)
target_include_directories(noisicaa-audioproc-vm PUBLIC ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-vm PRIVATE ${LIBLILV_LIBRARIES})
target_include_directories(noisicaa-audioproc-vm PRIVATE ${LIBCSOUND_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-vm PRIVATE ${LIBCSOUND_LIBRARIES})
target_include_directories(noisicaa-audioproc-vm PRIVATE ${LIBFLUIDSYNTH_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-vm PRIVATE ${LIBFLUIDSYNTH_LIBRARIES})
target_include_directories(noisicaa-audioproc-vm PRIVATE ${LIBSNDFILE_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-vm PRIVATE ${LIBSNDFILE_LIBRARIES})
target_include_directories(noisicaa-audioproc-vm PRIVATE ${LIBAVUTIL_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-vm PRIVATE ${LIBAVUTIL_LIBRARIES})
target_include_directories(noisicaa-audioproc-vm PRIVATE ${LIBSWRESAMPLE_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-vm PRIVATE ${LIBSWRESAMPLE_LIBRARIES})

add_cython_module(audio_stream CXX)
target_link_libraries(${audio_stream.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(spec CXX)
target_link_libraries(${spec.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(buffers CXX)
target_link_libraries(${buffers.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(control_value CXX)
target_link_libraries(${control_value.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(processor CXX)
target_link_libraries(${processor.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(processor_spec CXX)
target_link_libraries(${processor_spec.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(host_data CXX)
target_link_libraries(${host_data.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(block_context CXX)
target_link_libraries(${block_context.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(backend CXX)
target_link_libraries(${backend.so} PRIVATE noisicaa-audioproc-vm)

add_cython_module(engine CXX)
target_link_libraries(${engine.so} PRIVATE noisicaa-audioproc-vm)

foreach(TEST_SRC ${TEST_SRCS})
  string(REGEX REPLACE "\.pyx$" "" TEST_MOD ${TEST_SRC})
  add_cython_module(${TEST_MOD} CXX)
  target_link_libraries(${${TEST_MOD}.so} PRIVATE noisicaa-audioproc-vm)
  target_include_directories(${${TEST_MOD}.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
  target_link_libraries(${${TEST_MOD}.so} PRIVATE ${LIBLILV_LIBRARIES})
endforeach(TEST_SRC)
