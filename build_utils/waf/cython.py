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


def configure(ctx):
    ctx.find_program('cython')


class compile_cy_cmodule(Task):
    # def scan(self):
    #     ctx = self.generator.bld

    #     deps = []
    #     for line in self.inputs[0].read().splitlines():
    #         m = re.match(r'import\s+"([^"]*)"\s*;', line)
    #         if m:
    #             deps.append(ctx.srcnode.find_resource(m.group(1)))
    #     return (deps, None)

    def run(self):
        ctx = self.generator.bld

        cmd = [
            ctx.env.CYTHON[0],
            '--cplus',
            '-3',
            '-I', ctx.out_dir,
            '-I', ctx.top_dir,
            '-o', self.outputs[0].abspath(),
            self.inputs[0].abspath(),
        ]
        self.exec_command(cmd)


@conf
def cy_module(ctx, source, use=None):
    assert source.endswith('.pyx')

    source = ctx.path.make_node(source)
    cpp_source = source.change_ext('.pyx.cpp').get_bld()
    mod = source.change_ext('.so').get_bld()
    pxd = source.change_ext('.pxd').get_src()
    pyi = source.change_ext('.pyi').get_src()

    task = compile_cy_cmodule(env=ctx.env)
    task.set_inputs(source)
    task.set_outputs(cpp_source)
    ctx.add_to_group(task)

    ctx.shlib(
        target=mod,
        source=[cpp_source],
        includes=[
            ctx.srcnode,
            ctx.bldnode,
        ],
        use=['PYEXT'] + (use if use else []),
    )

    if pxd.exists():
        ctx.static_file(pxd)

    if pyi.exists():
        ctx.static_file(pyi)

@conf
def cy_test(ctx, source, use=None):
    old_grp = ctx.current_group
    ctx.set_group('tests')
    try:
        ctx.cy_module(source, use=use)
    finally:
        ctx.set_group(old_grp)
