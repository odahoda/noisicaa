add_python_package(
  callbacks.py
  callbacks_test.py
  fileutil.py
  fileutil_test.py
  ipc.py
  ipc_test.py
  message.py
  message_test.py
  model_base.py
  perf_stats_test.py
  process_manager.py
  process_manager_test.py
  recordfile.py
  recordfile_test.py
  stats_test.py
  storage.py
  storage_test.py
)

add_cython_module(logging_test CXX)
target_link_libraries(${logging_test.so} PRIVATE noisicaa-core)

set(LIB_SRCS
  logging.cpp
  perf_stats.cpp
)

add_cpp_capnp(message.capnp)
add_py_capnp(message.capnp)
add_cpp_capnp(perf_stats.capnp)
add_py_capnp(perf_stats.capnp)

add_library(noisicaa-core SHARED ${LIB_SRCS} message.capnp.c++ perf_stats.capnp.c++)

add_cython_module(perf_stats CXX)
target_link_libraries(${perf_stats.so} PRIVATE noisicaa-core)

add_cython_module(logging CXX)
target_link_libraries(${logging.so} PRIVATE noisicaa-core)

add_subdirectory(stats)
