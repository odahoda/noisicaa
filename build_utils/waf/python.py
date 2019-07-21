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
import os
import os.path
import py_compile
import shutil

from waflib.Configure import conf
from waflib.Task import Task
from waflib import Logs


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

    if ctx.in_group(ctx.GRP_BUILD_MAIN):
        ctx.install_files(
            os.path.join(ctx.env.LIBDIR, target_node.parent.relpath()), target_node)
        ctx.install_files(
            os.path.join(ctx.env.LIBDIR, compiled_node.parent.relpath()), compiled_node)

    return target_node


class run_py_test(Task):
    always_run = True

    def __init__(self, *, env, timeout=None):
        super().__init__(env=env)

        self.__timeout = timeout or 10
        assert self.__timeout > 0

    def __str__(self):
        return self.inputs[0].relpath()

    def keyword(self):
        return 'Testing'

    def run(self):
        ctx = self.generator.bld

        mod_path = self.inputs[0].relpath()
        assert mod_path.endswith('.py')
        mod_name = '.'.join(mod_path[:-3].split(os.sep))

        cmd = [
            ctx.env.PYTHON[0],
            '-m', 'noisidev.test_runner',
            '--store-result=%s' % os.path.join(ctx.TEST_RESULTS_PATH, mod_name),
            mod_name,
        ]
        self.exec_command(
            cmd,
            cwd=ctx.out_dir,
            timeout=self.__timeout)
        if not os.path.isfile(os.path.join(ctx.TEST_RESULTS_PATH, mod_name, 'results.xml')):
            Logs.info("Missing results.xml.")
            return 1

@conf
def py_test(ctx, source, timeout=None):
    if not ctx.env.ENABLE_TEST:
        return

    with ctx.group(ctx.GRP_BUILD_TESTS):
        target = ctx.py_module(source)

    with ctx.group(ctx.GRP_RUN_TESTS):
        if ctx.cmd == 'test':
            task = run_py_test(env=ctx.env, timeout=timeout)
            task.set_inputs(target)
            ctx.add_to_group(task)
