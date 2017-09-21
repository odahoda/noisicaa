add_python_package(
  audio_stream_test.py
)

set(LIB_SRCS
  audio_stream.cpp
  backend.cpp
  backend_ipc.cpp
  backend_null.cpp
  backend_portaudio.cpp
  buffers.cpp
  host_data.cpp
  host_system_lv2.cpp
  misc.cpp
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
  spec_test.pyx
  vm_test.pyx
)

add_cpp_capnp(block_data.capnp)
add_py_capnp(block_data.capnp)

add_library(noisicore SHARED ${LIB_SRCS} block_data.capnp.c++)
target_compile_options(noisicore PRIVATE -fPIC -std=c++11 -Wall -Werror -pedantic -DHAVE_PTHREAD_SPIN_LOCK)
target_link_libraries(noisicore PRIVATE noisicaa-core)
target_link_libraries(noisicore PRIVATE noisicaa-lv2)
target_link_libraries(noisicore PRIVATE capnp)
target_link_libraries(noisicore PRIVATE pthread)
target_link_libraries(noisicore PRIVATE portaudio)
target_include_directories(noisicore PUBLIC ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(noisicore PRIVATE ${LIBLILV_LIBRARIES})
target_include_directories(noisicore PRIVATE ${LIBCSOUND_INCLUDE_DIRS})
target_link_libraries(noisicore PRIVATE ${LIBCSOUND_LIBRARIES})
target_include_directories(noisicore PRIVATE ${LIBFLUIDSYNTH_INCLUDE_DIRS})
target_link_libraries(noisicore PRIVATE ${LIBFLUIDSYNTH_LIBRARIES})

add_cython_module(audio_stream CXX)
target_link_libraries(${audio_stream.so} PRIVATE noisicore)

add_cython_module(status CXX)
target_link_libraries(${status.so} PRIVATE noisicore)

add_cython_module(spec CXX)
target_link_libraries(${spec.so} PRIVATE noisicore)

add_cython_module(buffers CXX)
target_link_libraries(${buffers.so} PRIVATE noisicore)

add_cython_module(processor CXX)
target_link_libraries(${processor.so} PRIVATE noisicore)

add_cython_module(processor_spec CXX)
target_link_libraries(${processor_spec.so} PRIVATE noisicore)

add_cython_module(host_data CXX)
target_link_libraries(${host_data.so} PRIVATE noisicore)

add_cython_module(block_context CXX)
target_link_libraries(${block_context.so} PRIVATE noisicore)

add_cython_module(backend CXX)
target_link_libraries(${backend.so} PRIVATE noisicore)

foreach(TEST_SRC ${TEST_SRCS})
  string(REGEX REPLACE "\.pyx$" "" TEST_MOD ${TEST_SRC})
  add_cython_module(${TEST_MOD} CXX)
  target_link_libraries(${${TEST_MOD}.so} PRIVATE noisicore)
  target_include_directories(${${TEST_MOD}.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
  target_link_libraries(${${TEST_MOD}.so} PRIVATE ${LIBLILV_LIBRARIES})
endforeach(TEST_SRC)
