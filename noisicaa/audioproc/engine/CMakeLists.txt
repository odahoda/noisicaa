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
  backend_test.py
  engine_perftest.py
  engine_test.py
  graph.py
  plugin_host_process.py
  plugin_host_process_test.py
  plugin_host_test.py
  plugin_host_ladspa_test.py
  plugin_host_lv2_test.py
  processor_test.py
  processor_csound_test.py
  processor_cvgenerator_test.py
  processor_fluidsynth_test.py
  processor_pianoroll_test.py
  processor_plugin_test.py
  processor_sample_player_test.py
  processor_sample_script_test.py
  processor_sound_file_test.py
  processor_track_mixer_test.py
  realm_test.py
)

set(LIB_SRCS
  backend.cpp
  backend_null.cpp
  backend_portaudio.cpp
  backend_renderer.cpp
  block_context.cpp
  buffer_arena.cpp
  buffers.cpp
  control_value.cpp
  double_buffered_state_manager.cpp
  misc.cpp
  message_queue.cpp
  opcodes.cpp
  player.cpp
  plugin_host.pb.cc
  plugin_host.cpp
  plugin_host_lv2.cpp
  plugin_host_ladspa.cpp
  plugin_ui_host.cpp
  plugin_ui_host_lv2.cpp
  processor.cpp
  processor.pb.cc
  processor_null.cpp
  processor_csound_base.cpp
  processor_csound.cpp
  processor_custom_csound.cpp
  processor_fluidsynth.cpp
  processor_plugin.cpp
  processor_sample_player.cpp
  processor_sound_file.cpp
  processor_track_mixer.cpp
  processor_pianoroll.cpp
  processor_cvgenerator.cpp
  processor_sample_script.cpp
  spec.cpp
  realm.cpp
)

set(TEST_SRCS
  buffers_test.pyx
  opcodes_test.pyx
  player_test.pyx
  spec_test.pyx
)

py_proto(plugin_host.proto)
cpp_proto(plugin_host.proto)

py_proto(processor.proto)
cpp_proto(processor.proto)

add_library(noisicaa-audioproc-engine SHARED ${LIB_SRCS})
target_compile_options(noisicaa-audioproc-engine PRIVATE -fPIC -std=c++11 -Wall -Werror -pedantic -DHAVE_PTHREAD_SPIN_LOCK)
target_link_libraries(noisicaa-audioproc-engine PRIVATE noisicaa-core)
target_link_libraries(noisicaa-audioproc-engine PRIVATE noisicaa-host_system)
target_link_libraries(noisicaa-audioproc-engine PRIVATE noisicaa-lv2)
target_link_libraries(noisicaa-audioproc-engine PRIVATE noisicaa-node_db)
target_link_libraries(noisicaa-audioproc-engine PRIVATE noisicaa-audioproc-public)
target_link_libraries(noisicaa-audioproc-engine PRIVATE capnp)
target_link_libraries(noisicaa-audioproc-engine PRIVATE pthread)
target_link_libraries(noisicaa-audioproc-engine PRIVATE rt)
target_include_directories(noisicaa-audioproc-engine PUBLIC ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBLILV_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBCSOUND_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBCSOUND_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBFLUIDSYNTH_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBFLUIDSYNTH_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBSNDFILE_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBSNDFILE_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBAVUTIL_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBAVUTIL_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBSWRESAMPLE_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBSWRESAMPLE_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBPROTOBUF_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBPROTOBUF_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${LIBPORTAUDIO_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBPORTAUDIO_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PUBLIC ${LIBSUIL_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${LIBSUIL_LIBRARIES})
target_include_directories(noisicaa-audioproc-engine PRIVATE ${GTK2_INCLUDE_DIRS})
target_link_libraries(noisicaa-audioproc-engine PRIVATE ${GTK2_LIBRARIES})

add_cython_module(spec CXX)
target_link_libraries(${spec.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(buffer_arena CXX)
target_link_libraries(${buffer_arena.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(buffers CXX)
target_link_libraries(${buffers.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(control_value CXX)
target_link_libraries(${control_value.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(processor CXX)
target_link_libraries(${processor.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(block_context CXX)
target_link_libraries(${block_context.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(backend CXX)
target_link_libraries(${backend.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(engine CXX)
target_link_libraries(${engine.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(message_queue CXX)
target_link_libraries(${message_queue.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(plugin_host CXX)
target_link_libraries(${plugin_host.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(plugin_ui_host CXX)
target_link_libraries(${plugin_ui_host.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(realm CXX)
target_link_libraries(${realm.so} PRIVATE noisicaa-audioproc-engine)

add_cython_module(player CXX)
target_link_libraries(${player.so} PRIVATE noisicaa-audioproc-engine)

foreach(TEST_SRC ${TEST_SRCS})
  string(REGEX REPLACE "\.pyx$" "" TEST_MOD ${TEST_SRC})
  add_cython_module(${TEST_MOD} CXX)
  target_link_libraries(${${TEST_MOD}.so} PRIVATE noisicaa-audioproc-engine)
  target_include_directories(${${TEST_MOD}.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
  target_link_libraries(${${TEST_MOD}.so} PRIVATE ${LIBLILV_LIBRARIES})
endforeach(TEST_SRC)
