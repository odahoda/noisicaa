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
  node_description_registry.py
  ui_registry.py
  model_registry.py
)

py_proto(model_registry.proto)
add_dependencies(noisicaa.builtin_nodes.model_registry.proto noisicaa.builtin_nodes.midi_source.model.proto)
add_dependencies(noisicaa.builtin_nodes.model_registry.proto noisicaa.builtin_nodes.beat_track.model.proto)

py_proto(processor_message_registry.proto)
cpp_proto(processor_message_registry.proto)

add_library(noisicaa-builtin_nodes-processor_message_registry SHARED processor_message_registry.pb.cc)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-audioproc-public)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-control_track-processor_messages)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-sample_track-processor_messages)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-instrument-processor_messages)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-pianoroll-processor_messages)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-midi_source-processor_messages)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-midi_cc_to_cv-processor_messages)
target_link_libraries(noisicaa-builtin_nodes-processor_message_registry PRIVATE noisicaa-builtin_nodes-midi_looper-processor_messages)

add_library(noisicaa-builtin_nodes-processors SHARED processor_registry.cpp)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-control_track-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-sample_track-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-instrument-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-pianoroll-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-mixer-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-custom_csound-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-midi_source-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-oscillator-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-vca-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-noise-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-step_sequencer-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-midi_cc_to_cv-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-midi_looper-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-midi_monitor-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-metronome-processor)
target_link_libraries(noisicaa-builtin_nodes-processors PRIVATE noisicaa-builtin_nodes-midi_velocity_mapper-processor)

add_subdirectory(score_track)
add_subdirectory(beat_track)
add_subdirectory(control_track)
add_subdirectory(sample_track)
add_subdirectory(instrument)
add_subdirectory(pianoroll)
add_subdirectory(mixer)
add_subdirectory(custom_csound)
add_subdirectory(midi_source)
add_subdirectory(oscillator)
add_subdirectory(vca)
add_subdirectory(noise)
add_subdirectory(step_sequencer)
add_subdirectory(midi_cc_to_cv)
add_subdirectory(midi_looper)
add_subdirectory(midi_monitor)
add_subdirectory(metronome)
add_subdirectory(midi_velocity_mapper)
