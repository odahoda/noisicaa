# -*- mode: python -*-

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import importlib.util
import os.path
import py_compile
import re
import shutil

from waflib.Configure import conf
from waflib.Task import Task

top = '.'
out = 'build'


def options(ctx):
    ctx.load('compiler_cxx')
    ctx.load('python')


def configure(ctx):
    ctx.load('compiler_cxx')
    ctx.load('python')
    ctx.load('proto', tooldir='waftools')
    ctx.load('python', tooldir='waftools')
    ctx.load('model', tooldir='waftools')
    ctx.load('static', tooldir='waftools')
    ctx.load('csound', tooldir='waftools')
    ctx.load('sf2', tooldir='waftools')

    ctx.check_python_version(minver=(3, 5))
    ctx.check_python_headers()


def build(ctx):
    ctx.add_group('noisidev')
    ctx.recurse('noisidev')

    ctx.add_group('noisicaa')
    ctx.recurse('noisicaa')
    ctx.recurse('data')
    ctx.recurse('testdata')


# find_package(Cython REQUIRED)

# if("$ENV{VIRTUAL_ENV}" STREQUAL "")
# message(FATAL_ERROR "Not running in a virtual env.")
# endif("$ENV{VIRTUAL_ENV}" STREQUAL "")

# find_package(PythonLibs REQUIRED)
# include_directories(${PYTHON_INCLUDE_DIRS})

# set(ENV{PKG_CONFIG_PATH} $ENV{VIRTUAL_ENV}/lib/pkgconfig)
# find_package(PkgConfig)
# pkg_check_modules(LIBSRATOM REQUIRED sratom-0)
# pkg_check_modules(LIBLILV REQUIRED lilv-0)
# pkg_check_modules(LIBSUIL REQUIRED suil-0>=0.10.0)
# pkg_check_modules(LIBSNDFILE REQUIRED sndfile)
# pkg_check_modules(LIBFLUIDSYNTH REQUIRED fluidsynth>=1.1.6)
# pkg_check_modules(LIBAVUTIL REQUIRED libavutil)
# pkg_check_modules(LIBSWRESAMPLE REQUIRED libswresample)
# pkg_check_modules(LIBPROTOBUF REQUIRED protobuf>=3.7)
# pkg_check_modules(LIBPORTAUDIO REQUIRED portaudio-2.0>=19)
# pkg_check_modules(LIBUNWIND REQUIRED libunwind-generic>=1.1)

# find_package(Qt4 4.8 REQUIRED QtGui)
# find_package(GTK2 2.24 REQUIRED gtk)

# set(LIBCSOUND_INCLUDE_DIRS)
# set(LIBCSOUND_LIBRARIES csound64)

# add_compile_options(-O2 -g -std=c++11)
# include_directories(${CMAKE_SOURCE_DIR})
# include_directories(${CMAKE_BINARY_DIR})
# include_directories($ENV{VIRTUAL_ENV}/include)
# link_directories($ENV{VIRTUAL_ENV}/lib)

# macro(install_files target)
#   foreach(src ${ARGN})
#     add_custom_command(
#       OUTPUT ${src}
#       COMMAND ln -sf ${CMAKE_CURRENT_LIST_DIR}/${src} ${src}
#       DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
#       )
#   endforeach(src)
#   add_custom_target(${target} ALL DEPENDS ${ARGN})
# endmacro(install_files)

# macro(install_svg target)
#   foreach(src ${ARGN})
#     add_custom_command(
#       OUTPUT ${src}
#       COMMAND PYTHONPATH=${CMAKE_SOURCE_DIR} python -m noisidev.process_svg -o ${src} ${CMAKE_CURRENT_LIST_DIR}/${src}
#       DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
#       )
#   endforeach(src)
#   add_custom_target(${target} ALL DEPENDS ${ARGN})
# endmacro(install_svg)

# macro(add_cython_module mod lang)
#   file(RELATIVE_PATH pkg_path ${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_LIST_DIR})
#   string(REGEX REPLACE "/" "." pkg_target ${pkg_path})
#   add_cython_target(${mod} ${mod}.pyx ${lang} PY3)
#   add_library(${pkg_target}.${mod} MODULE ${${mod}})
#   set_target_properties(${pkg_target}.${mod} PROPERTIES PREFIX "" OUTPUT_NAME ${mod})
#   set(${mod}.so ${pkg_target}.${mod})
# endmacro(add_cython_module)

# macro(py_proto src)
#   string(REGEX REPLACE "\\.proto$" "" base ${src})
#   file(RELATIVE_PATH pkg_path ${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_LIST_DIR})
#   add_custom_command(
#     OUTPUT ${base}_pb2.py
#     COMMAND LD_LIBRARY_PATH=$ENV{VIRTUAL_ENV}/lib $ENV{VIRTUAL_ENV}/bin/protoc --python_out=${CMAKE_BINARY_DIR} --mypy_out=${CMAKE_BINARY_DIR} --proto_path=${CMAKE_SOURCE_DIR} --proto_path=${CMAKE_BINARY_DIR} ${pkg_path}/${src}
#     DEPENDS ${src}
#   )
#   string(REGEX REPLACE "/" "." pkg_target ${pkg_path})
#   add_custom_target(${pkg_target}.${src} ALL DEPENDS ${base}_pb2.py)
# endmacro(py_proto)

# macro(cpp_proto src)
#   string(REGEX REPLACE "\\.proto$" "" base ${src})
#   add_custom_command(
#     OUTPUT ${base}.pb.cc ${base}.pb.h
#     COMMAND LD_LIBRARY_PATH=$ENV{VIRTUAL_ENV}/lib $ENV{VIRTUAL_ENV}/bin/protoc --cpp_out=${CMAKE_BINARY_DIR} --proto_path=${CMAKE_SOURCE_DIR} --proto_path=${CMAKE_BINARY_DIR} ${pkg_path}/${src}
#     DEPENDS ${src}
#   )
# endmacro(cpp_proto)

# macro(static_file src)
#   add_custom_command(
#     OUTPUT ${src}
#     COMMAND mkdir -p "$$(dirname" ${src} ")" && cp -f ${CMAKE_CURRENT_LIST_DIR}/${src} ${src}
#     DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
#   )
# endmacro(static_file)

# macro(faust_dsp clsName src)
#   string(REGEX REPLACE "\\.dsp$" "" base ${src})
#   add_custom_command(
#     OUTPUT ${base}.cpp ${base}.h ${base}.json
#     COMMAND bin/build-faust-processor ${clsName} ${CMAKE_CURRENT_LIST_DIR}/${src} ${CMAKE_CURRENT_BINARY_DIR}
#     WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
#     DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
#   )
# endmacro(faust_dsp)

