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
