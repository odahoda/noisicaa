add_python_package(
  ast.py
  buffers_test.py
  compiler.py
  compiler_test.py
  engine_perftest.py
  engine_test.py
  graph.py
  spec.py
)

add_cython_module(engine C)
add_cython_module(buffers C)
