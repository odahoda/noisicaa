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
  node_description.py
  model.py
  model_test.py
  node_ui.py
  node_ui_test.py
  processor_test.py
  processor_messages.py
)

py_proto(model.proto)
cpp_proto(model.proto)
py_proto(processor.proto)
cpp_proto(processor.proto)
py_proto(processor_messages.proto)
cpp_proto(processor_messages.proto)

add_library(noisicaa-builtin_nodes-midi_cc_to_cv-processor_messages SHARED processor_messages.pb.cc)
target_link_libraries(noisicaa-builtin_nodes-midi_cc_to_cv-processor_messages PRIVATE noisicaa-audioproc-public)

add_library(noisicaa-builtin_nodes-midi_cc_to_cv-processor SHARED processor.cpp processor.pb.cc)
target_compile_options(noisicaa-builtin_nodes-midi_cc_to_cv-processor PRIVATE -fPIC -std=c++11 -Wall -Werror -pedantic -DHAVE_PTHREAD_SPIN_LOCK)
target_link_libraries(noisicaa-builtin_nodes-midi_cc_to_cv-processor PRIVATE noisicaa-audioproc-public)
target_link_libraries(noisicaa-builtin_nodes-midi_cc_to_cv-processor PRIVATE noisicaa-host_system)
target_link_libraries(noisicaa-builtin_nodes-midi_cc_to_cv-processor PRIVATE noisicaa-builtin_nodes-processor_message_registry)
target_link_libraries(noisicaa-builtin_nodes-midi_cc_to_cv-processor PRIVATE noisicaa-builtin_nodes-midi_cc_to_cv-processor_messages)
