add_python_package(
  atom_test.py
)

add_cython_module(atom CXX)
add_cython_module(core CXX)
add_cython_module(urid CXX)
target_link_libraries(${urid.so} PRIVATE noisicaa-lv2)
add_cython_module(worker CXX)
add_cython_module(bufsize CXX)
add_cython_module(options CXX)
