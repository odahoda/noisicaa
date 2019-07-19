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

from waflib.Configure import conf
from waflib.Task import Task


def configure(ctx):
    ctx.find_program('protoc')


class compile_py_proto(Task):
    def __str__(self):
        return self.outputs[0].relpath()

    def keyword(self):
        return 'Generating'

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

        cmd = [
            ctx.env.PROTOC[0],
            '--python_out=' + ctx.out_dir,
            '--mypy_out=quiet:' + ctx.out_dir,
            '--proto_path=' + ctx.top_dir,
            '--proto_path=' + ctx.out_dir,
            self.inputs[0].relpath(),
        ]
        rc = self.exec_command(cmd, cwd=ctx.top_dir)
        if rc:
            return

        py_compile.compile(
            self.outputs[0].abspath(), self.outputs[1].abspath(), doraise=True, optimize=0)

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
    def __str__(self):
        return self.outputs[0].relpath()

    def keyword(self):
        return 'Generating'

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
        return self.exec_command(cmd, cwd=ctx.top_dir)

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
