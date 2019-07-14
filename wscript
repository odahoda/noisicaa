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
    ctx.find_program('protoc')

    ctx.check_python_version(minver=(3, 5))
    ctx.check_python_headers()


def copy_file(task):
    assert len(task.inputs) == 1
    assert len(task.outputs) == 1
    shutil.copyfile(task.inputs[0].abspath(), task.outputs[0].abspath())

def copy_py_module(task):
    assert len(task.inputs) == 1
    assert 1 <= len(task.outputs) <= 2
    shutil.copyfile(task.inputs[0].abspath(), task.outputs[0].abspath())
    if len(task.outputs) > 1:
        py_compile.compile(task.outputs[0].abspath(), task.outputs[1].abspath(), doraise=True, optimize=0)


@conf
def py_module(ctx, source):
    source_node = ctx.path.make_node(source)
    target_node = ctx.path.get_bld().make_node(source)

    targets = [target_node]
    if source.endswith('.py'):
        compiled_node = ctx.path.get_bld().make_node(importlib.util.cache_from_source(source, optimization=''))
        targets.append(compiled_node)

    ctx(rule=copy_py_module,
        source=source_node,
        target=targets,
    )


@conf
def py_test(ctx, source):
    source_node = ctx.path.make_node(source)
    target_node = ctx.path.get_bld().make_node(source)

    targets = [target_node]
    if source.endswith('.py'):
        compiled_node = ctx.path.get_bld().make_node(importlib.util.cache_from_source(source, optimization=''))
        targets.append(compiled_node)

    ctx(rule=copy_py_module,
        source=source_node,
        target=targets,
    )


class compile_py_proto(Task):
    def scan(self):
        ctx = self.generator.bld

        deps = []
        for line in self.inputs[0].read().splitlines():
            m = re.match(r'import\s+"([^"]*)"\s*;', line)
            if m:
                deps.append(ctx.srcnode.find_resource(m.group(1)))
        return (deps, None)

    def run(self):
        ctx = self.generator.bld

        #LIBRARY_PATH=$ENV{VIRTUAL_ENV}/lib
        cmd = [
            ctx.env.PROTOC[0],
            '--python_out=' + ctx.out_dir,
            '--mypy_out=quiet:' + ctx.out_dir,
            '--proto_path=' + ctx.top_dir,
            '--proto_path=' + ctx.out_dir,
            self.inputs[0].relpath(),
        ]
        self.exec_command(cmd, cwd=ctx.top_dir)

        py_compile.compile(self.outputs[0].abspath(), self.outputs[1].abspath(), doraise=True, optimize=0)

@conf
def py_proto(ctx, source):
    assert source.endswith('.proto')

    task = compile_py_proto(env=ctx.env)
    task.set_inputs(ctx.path.find_resource(source))
    pb2_path = os.path.splitext(source)[0] + '_pb2.py'
    task.set_outputs(ctx.path.get_bld().make_node(pb2_path))
    task.set_outputs(ctx.path.get_bld().make_node(
        importlib.util.cache_from_source(pb2_path, optimization='')))
    task.set_outputs(ctx.path.get_bld().make_node(
        os.path.splitext(source)[0] + '_pb2.pyi'))
    ctx.add_to_group(task)


class compile_cpp_proto(Task):
    def scan(self):
        ctx = self.generator.bld

        deps = []
        for line in self.inputs[0].read().splitlines():
            m = re.match(r'import\s+"([^"]*)"\s*;', line)
            if m:
                deps.append(ctx.srcnode.find_resource(m.group(1)))
        return (deps, None)

    def run(self):
        ctx = self.generator.bld

        #LIBRARY_PATH=$ENV{VIRTUAL_ENV}/lib
        cmd = [
            ctx.env.PROTOC[0],
            '--cpp_out=' + ctx.out_dir,
            '--proto_path=' + ctx.top_dir,
            '--proto_path=' + ctx.out_dir,
            self.inputs[0].relpath(),
        ]
        self.exec_command(cmd, cwd=ctx.top_dir)

@conf
def cpp_proto(ctx, source):
    assert source.endswith('.proto')

    task = compile_cpp_proto(env=ctx.env)
    task.set_inputs(ctx.path.find_resource(source))
    task.set_outputs(ctx.path.get_bld().make_node(
        os.path.splitext(source)[0] + '.pb.cc'))
    task.set_outputs(ctx.path.get_bld().make_node(
        os.path.splitext(source)[0] + '.pb.h'))
    ctx.add_to_group(task)


def build_model(task):
    ctx = task.generator.bld
    cmd = [
        ctx.env.PYTHON[0],
        'noisidev/build_model.py',
        '--output', ctx.out_dir,
        '--template', task.inputs[1].abspath(),
        os.path.relpath(task.inputs[0].abspath(), ctx.top_dir),
    ]
    task.exec_command(cmd, cwd=ctx.top_dir, env={'PYTHONPATH': ctx.out_dir})


@conf
def model_description(ctx, source, *, output='_model.py', template='noisicaa/builtin_nodes/model.tmpl.py'):
    ctx(rule=build_model,
        source=[
            ctx.path.make_node(source),
            ctx.srcnode.make_node(template),
        ],
        target=[
            ctx.path.get_bld().make_node(output),
            ctx.path.get_bld().make_node(
                os.path.join(os.path.dirname(output), 'model.proto')),
        ],
    )


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

# macro(render_csound src dest)
#   add_custom_command(
#     OUTPUT ${dest}
#     COMMAND LD_LIBRARY_PATH=$ENV{VIRTUAL_ENV}/lib csound -o${dest} ${CMAKE_CURRENT_LIST_DIR}/${src}
#     DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
#   )
# endmacro(render_csound)

# macro(faust_dsp clsName src)
#   string(REGEX REPLACE "\\.dsp$" "" base ${src})
#   add_custom_command(
#     OUTPUT ${base}.cpp ${base}.h ${base}.json
#     COMMAND bin/build-faust-processor ${clsName} ${CMAKE_CURRENT_LIST_DIR}/${src} ${CMAKE_CURRENT_BINARY_DIR}
#     WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
#     DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
#   )
# endmacro(faust_dsp)

