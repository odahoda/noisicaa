add_python_package(
  audioproc_client.py
  audioproc_client_test.py
  audioproc_process.py
  data.py
  exceptions.py
  mutations.py
  node.py
  node_db.py
  ports.py
)

add_py_capnp(pipeline_mutations.capnp)

add_subdirectory(nodes)
add_subdirectory(vm)

file(COPY testdata DESTINATION .)
