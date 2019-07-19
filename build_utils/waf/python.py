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
import py_compile
import shutil

from waflib.Configure import conf


def copy_py_module(task):
    assert len(task.inputs) == 1
    assert 1 <= len(task.outputs) <= 2
    shutil.copyfile(task.inputs[0].abspath(), task.outputs[0].abspath())
    shutil.copymode(task.inputs[0].abspath(), task.outputs[0].abspath())
    if len(task.outputs) > 1:
        py_compile.compile(
            task.outputs[0].abspath(), task.outputs[1].abspath(), doraise=True, optimize=0)


@conf
def py_module(ctx, source):
    assert source.endswith('.py')

    source_node = ctx.path.make_node(source)
    target_node = ctx.path.get_bld().make_node(source)
    compiled_node = ctx.path.get_bld().make_node(
        importlib.util.cache_from_source(source, optimization=''))

    ctx(rule=copy_py_module,
        source=source_node,
        target=[
            target_node,
            compiled_node,
        ])


@conf
def py_test(ctx, source):
    if not ctx.env.ENABLE_TEST:
        return

    old_grp = ctx.current_group
    ctx.set_group('tests')
    try:
        ctx.py_module(source)
    finally:
        ctx.set_group(old_grp)
