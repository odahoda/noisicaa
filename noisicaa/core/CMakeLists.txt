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
  perf_stats.py
  perf_stats_test.py
  process_manager.py
  process_manager_test.py
  recordfile.py
  recordfile_test.py
  stats_test.py
  storage.py
  storage_test.py
)

add_capnp(message.capnp)
add_capnp(perf_stats.capnp)

add_subdirectory(stats)
