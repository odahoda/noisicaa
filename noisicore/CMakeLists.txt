add_python_package()

set(LIB_SRCS
  vm.cpp
  opcodes.cpp
  spec.cpp
  misc.cpp
  buffers.cpp
)

set(TEST_SRCS
  vm_test.pyx
  spec_test.pyx
  buffers_test.pyx
)

include_directories(${CMAKE_CURRENT_LIST_DIR})

add_library(noisicore STATIC ${LIB_SRCS})
target_compile_options(noisicore PRIVATE -fPIC)

foreach(TEST_SRC ${TEST_SRCS})
  string(REGEX REPLACE "\.pyx$" "" TEST_MOD ${TEST_SRC})
  add_cython_module(${TEST_MOD} CXX)
  target_link_libraries(${${TEST_MOD}.so} noisicore)
endforeach(TEST_SRC)
