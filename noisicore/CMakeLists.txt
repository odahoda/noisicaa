add_python_package()

set(LIB_SRCS
  backend.cpp
  buffers.cpp
  misc.cpp
  opcodes.cpp
  spec.cpp
  vm.cpp
)

set(TEST_SRCS
  backend_test.pyx
  buffers_test.pyx
  spec_test.pyx
  vm_test.pyx
)

include_directories(${CMAKE_CURRENT_LIST_DIR})

add_library(noisicore STATIC ${LIB_SRCS})
target_compile_options(noisicore PRIVATE -fPIC -g)
target_link_libraries(noisicore PRIVATE portaudio)

foreach(TEST_SRC ${TEST_SRCS})
  string(REGEX REPLACE "\.pyx$" "" TEST_MOD ${TEST_SRC})
  add_cython_module(${TEST_MOD} CXX)
  target_link_libraries(${${TEST_MOD}.so} noisicore)
endforeach(TEST_SRC)
