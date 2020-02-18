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

import os.path
import subprocess
import sys

from waflib.Configure import conf
from waflib.Task import Task
from waflib import Utils


def configure(ctx):
    ctx.find_program('ffmpeg')


class ffmpeg_runner(Task):
    def __init__(self, args, **kwargs):
        super().__init__(**kwargs)
        self.__args = args

    def __str__(self):
        return self.outputs[0].relpath()

    def keyword(self):
        return 'Generating'

    def run(self):
        ctx = self.generator.bld
        cwd = ctx.srcnode

        cmd = [
            ctx.env.FFMPEG[0],
            '-y', '-nostdin',
            '-i', self.inputs[0].path_from(cwd)
        ]
        cmd.extend(self.__args)
        cmd.append(self.outputs[0].path_from(cwd))

        kw = {
            'cwd': cwd.abspath(),
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
        }
        ctx.log_command(cmd, kw)
        rc, out, _ = Utils.run_process(cmd, kw)
        if rc:
            sys.stderr.write(out.decode('utf-8'))
        return rc


@conf
def run_ffmpeg(ctx, target, source, args, install=None, install_to=None, chmod=0o644):
    target = ctx.path.get_bld().make_node(target)

    task = ffmpeg_runner(env=ctx.env, args=args)
    task.set_inputs(ctx.path.find_resource(source))
    task.set_outputs(target)
    ctx.add_to_group(task)

    if install is None:
        install = ctx.in_group(ctx.GRP_BUILD_MAIN)

    if install:
        if install_to is None:
            install_to = os.path.join(
                ctx.env.DATADIR, target.parent.path_from(ctx.bldnode.make_node('data')))

        ctx.install_files(install_to, target, chmod=chmod)
