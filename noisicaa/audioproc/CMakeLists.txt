add_python_package(
  audio_format_test.py
  audioproc_client.py
  audioproc_client_test.py
  audioproc_process.py
  backend.py
  data.py
  exceptions.py
  libfluidsynth.py
  mutations.py
  node.py
  node_db.py
  ports.py
  resample_test.py
)

add_py_capnp(pipeline_mutations.capnp)

add_cython_module(resample C)
target_link_libraries(${resample.so} PRIVATE swresample)

add_cython_module(audio_format C)

add_subdirectory(nodes)
add_subdirectory(vm)

file(COPY testdata DESTINATION .)
