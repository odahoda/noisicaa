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
import subprocess

from waflib.Configure import conf
from waflib.Task import Task


def configure(ctx):
    ctx.find_program('csound')


class compile_csound(Task):
    def __str__(self):
        return self.outputs[0].relpath()

    def keyword(self):
        return 'Generating'

    def run(self):
        ctx = self.generator.bld
        cwd = ctx.srcnode

        env = {
            'LD_LIBRARY_PATH': os.path.join(ctx.env.VIRTUAL_ENV, 'lib'),
        }

        cmd = [
            ctx.env.CSOUND[0],
            '-o' + self.outputs[0].path_from(cwd),
            self.inputs[0].path_from(cwd),
        ]
        self.exec_command(cmd, cwd=cwd, env=env)


@conf
def rendered_csound(ctx, source):
    assert source.endswith('.csnd')

    task = compile_csound(env=ctx.env)
    task.set_inputs(ctx.path.find_resource(source))
    wav_path = os.path.splitext(source)[0] + '.wav'
    task.set_outputs(ctx.path.get_bld().make_node(wav_path))
    ctx.add_to_group(task)
