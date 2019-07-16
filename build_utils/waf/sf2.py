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
import yaml


class mksf2(Task):
    def scan(self):
        ctx = self.generator.bld

        definition = yaml.load(self.inputs[0].read(), Loader=yaml.FullLoader)

        deps = []
        for instr in definition['instruments']:
            deps.append(self.inputs[0].parent.find_resource(instr['file']))
        return (deps, None)

    def run(self):
        ctx = self.generator.bld

        cmd = [
            ctx.env.PYTHON[0],
            ctx.srcnode.find_resource('build_utils/mksf2.py').abspath(),
            '--search_paths=.:' + self.inputs[0].parent.get_bld().abspath(),
            '--output=' + self.outputs[0].abspath(),
            self.inputs[0].abspath(),
        ]
        self.exec_command(cmd, env={'PYTHONPATH': ctx.bldnode.abspath()})


@conf
def build_sf2(ctx, source):
    assert source.endswith('.yaml')

    task = mksf2(env=ctx.env)
    task.set_inputs(ctx.path.find_resource(source))
    task.set_outputs(ctx.path.get_bld().make_node(
        os.path.splitext(source)[0] + '.sf2'))
    ctx.add_to_group(task)
