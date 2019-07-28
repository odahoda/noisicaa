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
import shutil

from waflib.Configure import conf
from waflib.Node import Node


def copy_file(task):
    assert len(task.inputs) == 1
    assert len(task.outputs) == 1

    if task.generator.rewrite:
        with open(task.inputs[0].abspath(), 'r') as fp:
            contents = fp.read()

        contents = contents.format(**task.generator.bld.env)

        with open(task.outputs[0].abspath(), 'w') as fp:
            fp.write(contents)
    else:
        shutil.copyfile(task.inputs[0].abspath(), task.outputs[0].abspath())
    shutil.copymode(task.inputs[0].abspath(), task.outputs[0].abspath())


@conf
def static_file(ctx, source, target=None, install=None, install_to=None, rewrite=False, chmod=0o644):
    if not isinstance(source, Node):
        source = ctx.path.make_node(source)

    if target is None:
        target = source.get_bld()

    if not isinstance(target, Node):
        target = ctx.path.make_node(target).get_bld()

    ctx(rule=copy_file,
        source=source,
        target=target,
        rewrite=rewrite)

    if install is None:
        install = ctx.in_group(ctx.GRP_BUILD_MAIN)

    if install:
        if install_to is None:
            install_to = os.path.join(
                ctx.env.DATADIR, target.parent.path_from(ctx.bldnode.make_node('data')))

        ctx.install_files(install_to, target, chmod=chmod)
