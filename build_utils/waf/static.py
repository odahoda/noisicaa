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

import shutil

from waflib.Configure import conf
from waflib.Node import Node


def copy_file(task):
    assert len(task.inputs) == 1
    assert len(task.outputs) == 1
    shutil.copyfile(task.inputs[0].abspath(), task.outputs[0].abspath())
    shutil.copymode(task.inputs[0].abspath(), task.outputs[0].abspath())


@conf
def static_file(ctx, source):
    if not isinstance(source, Node):
        source = ctx.path.make_node(source)

    ctx(rule=copy_file,
        source=source,
        target=source.get_bld(),
    )
