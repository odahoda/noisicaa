cmake_minimum_required(VERSION 3.5)
project (noisicaä)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR}/cmake)

find_package(Cython REQUIRED)

if("$ENV{VIRTUAL_ENV}" STREQUAL "")
message(FATAL_ERROR "Not running in a virtual env.")
endif("$ENV{VIRTUAL_ENV}" STREQUAL "")

find_package(PythonLibs REQUIRED)
include_directories(${PYTHON_INCLUDE_DIRS})

set(ENV{PKG_CONFIG_PATH} $ENV{VIRTUAL_ENV}/lib/pkgconfig)
find_package(PkgConfig)
pkg_check_modules(LIBSRATOM REQUIRED sratom-0)
pkg_check_modules(LIBLILV REQUIRED lilv-0)
pkg_check_modules(LIBSNDFILE REQUIRED sndfile)
pkg_check_modules(LIBFLUIDSYNTH REQUIRED fluidsynth)

set(LIBCSOUND_INCLUDE_DIRS)
set(LIBCSOUND_LIBRARIES csound64)

include_directories(${CMAKE_CURRENT_LIST_DIR})
include_directories($ENV{VIRTUAL_ENV}/include)
link_directories($ENV{VIRTUAL_ENV}/lib)

macro(add_python_package)
  foreach(src __init__.py ${ARGN})
    add_custom_command(
      OUTPUT ${src}
      COMMAND ln -sf ${CMAKE_CURRENT_LIST_DIR}/${src} ${src}
      DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
      )
  endforeach(src)
  file(RELATIVE_PATH pkg_path ${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_LIST_DIR})
  string(REGEX REPLACE "/" "." pkg_target ${pkg_path})
  add_custom_target("pkg-${pkg_target}" ALL DEPENDS __init__.py ${ARGN})
endmacro(add_python_package)

macro(add_cython_module mod lang)
  file(RELATIVE_PATH pkg_path ${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_LIST_DIR})
  string(REGEX REPLACE "/" "." pkg_target ${pkg_path})
  add_cython_target(${mod} ${mod}.pyx ${lang} PY3)
  add_library(${pkg_target}.${mod} MODULE ${${mod}})
  set_target_properties(${pkg_target}.${mod} PROPERTIES PREFIX "" OUTPUT_NAME ${mod})
  set(${mod}.so ${pkg_target}.${mod})
endmacro(add_cython_module)

macro(add_py_capnp src)
  add_custom_command(
    OUTPUT ${src}
    COMMAND ln -sf ${CMAKE_CURRENT_LIST_DIR}/${src} ${src}
    DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
    )
  file(RELATIVE_PATH pkg_path ${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_LIST_DIR})
  string(REGEX REPLACE "/" "." pkg_target ${pkg_path})
  add_custom_target(${pkg_target}.${src} ALL DEPENDS ${src})
endmacro(add_py_capnp)

macro(add_cpp_capnp src)
  add_custom_command(
    OUTPUT ${src}.c++ ${src}.h
    COMMAND capnp compile --verbose --output=c++:${CMAKE_BINARY_DIR} --src-prefix=${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_LIST_DIR}/${src}
    DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
  )
endmacro(add_cpp_capnp)

add_subdirectory(noisicore)
add_subdirectory(noisicaa)
add_subdirectory(noisidev)

file(COPY data DESTINATION .)
