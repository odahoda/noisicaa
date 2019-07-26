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

from waflib.Configure import conf
from waflib.Task import Task


class build_model(Task):
    def __str__(self):
        return self.outputs[0].relpath()

    def keyword(self):
        return 'Generating'

    def run(self):
        ctx = self.generator.bld
        cmd = [
            ctx.env.PYTHON[0],
            'build_utils/build_model.py',
            '--output', ctx.out_dir,
            '--template', self.inputs[1].abspath(),
            os.path.relpath(self.inputs[0].abspath(), ctx.top_dir),
        ]
        return self.exec_command(cmd, cwd=ctx.top_dir)


@conf
def model_description(
        ctx, source, *, output='_model.py', template='noisicaa/builtin_nodes/model.tmpl.py'):
    model_node = ctx.path.get_bld().make_node(output)

    task = build_model(env=ctx.env)
    task.set_inputs(ctx.path.make_node(source))
    task.set_inputs(ctx.srcnode.make_node(template))
    task.set_outputs(model_node)
    task.set_outputs(ctx.path.get_bld().make_node(
        os.path.join(os.path.dirname(output), 'model.proto')))
    ctx.add_to_group(task)

    if ctx.in_group(ctx.GRP_BUILD_MAIN):
        ctx.install_files(os.path.join(ctx.env.LIBDIR, model_node.parent.relpath()), model_node)
