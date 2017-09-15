add_python_package(
  ast.py
  compiler.py
  compiler_test.py
  engine_perftest.py
  engine_test.py
  graph.py
  spec.py
)

add_cython_module(engine CXX)
target_link_libraries(${engine.so} PRIVATE noisicore)
