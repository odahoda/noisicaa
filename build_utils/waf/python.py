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
import json
import os
import os.path
import py_compile
import re
import shutil
import subprocess
import sys
import threading

from waflib.Context import BOTH
from waflib.Configure import conf
from waflib.Task import Task
from waflib import Logs
from waflib import Utils
from waflib.Errors import WafError


def copy_py_module(task):
    assert len(task.inputs) == 1
    assert 1 <= len(task.outputs) <= 2
    shutil.copyfile(task.inputs[0].abspath(), task.outputs[0].abspath())
    shutil.copymode(task.inputs[0].abspath(), task.outputs[0].abspath())
    if len(task.outputs) > 1:
        py_compile.compile(
            task.outputs[0].abspath(), task.outputs[1].abspath(), doraise=True, optimize=0)


# Multiple concurrent mypy processes cannot share the same cache directory. So we track a set of
# directories and allocate an unused directory for each running process.
mypy_cache_lock = threading.Lock()
mypy_caches = []
mypy_next_cache = 0


class run_mypy(Task):
    always_run = True

    def __init__(self, *, env, strict):
        super().__init__(env=env)

        self.__strict = strict

    def __str__(self):
        return self.inputs[0].relpath()

    def keyword(self):
        return 'Lint (mypy)'

    def run(self):
        ctx = self.generator.bld

        mod_path = self.inputs[0].relpath()
        assert mod_path.endswith('.py') or mod_path.endswith('.so')
        mod_name = '.'.join(os.path.splitext(mod_path)[0].split(os.sep))

        ini_path = os.path.join(ctx.top_dir, 'noisidev', 'mypy.ini')

        with mypy_cache_lock:
            if not mypy_caches:
                global mypy_next_cache
                cache_num = mypy_next_cache
                mypy_next_cache += 1
            else:
                cache_num = mypy_caches.pop(-1)

        try:
            argv = [
                os.path.join(ctx.env.VIRTUAL_ENV, 'bin', 'mypy'),
                '--config-file', ini_path,
                '--cache-dir=%s' % os.path.join(ctx.out_dir, 'mypy-cache.%d' % cache_num),
                '--show-traceback',
                '-m', mod_name,
            ]
            if self.__strict:
                argv.append('--disallow-untyped-defs')

            env = dict(os.environ)
            env['MYPYPATH'] = os.path.join(ctx.top_dir, '3rdparty', 'typeshed')

            kw = {
                'cwd': ctx.out_dir,
                'env': env,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
            }

            ctx.log_command(argv, kw)
            rc, out, err = Utils.run_process(argv, kw)

        finally:
            with mypy_cache_lock:
                mypy_caches.append(cache_num)

        if err:
            sys.stderr.write(err.decode('utf-8'))
            ctx.fatal("mypy is unhappy")

        out_path = os.path.join(ctx.TEST_RESULTS_PATH, mod_name, 'mypy.log')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as fp:
            fp.write(out)


class run_pylint(Task):
    always_run = True

    def __str__(self):
        return self.inputs[0].relpath()

    def keyword(self):
        return 'Lint (pylint)'

    def run(self):
        ctx = self.generator.bld

        mod_path = self.inputs[0].relpath()
        assert mod_path.endswith('.py') or mod_path.endswith('.so')
        mod_name = '.'.join(os.path.splitext(mod_path)[0].split(os.sep))

        argv = [
            os.path.join(ctx.env.VIRTUAL_ENV, 'bin', 'pylint'),
            '--rcfile=%s' % os.path.join(ctx.top_dir, 'bin', 'pylintrc'),
            '--output-format=parseable',
            '--score=no',
            '--exit-zero',
            mod_name,
        ]

        kw = {
            'cwd': ctx.out_dir,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
        }

        ctx.log_command(argv, kw)
        rc, out, err = Utils.run_process(argv, kw)

        if rc != 0:
            sys.stderr.write(err.decode('utf-8'))
            ctx.fatal("pylint is unhappy")

        out_path = os.path.join(ctx.TEST_RESULTS_PATH, mod_name, 'pylint.log')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as fp:
            fp.write(out)


@conf
def py_module(ctx, source, mypy='strict', pylint='enabled'):
    assert source.endswith('.py')
    assert mypy in ('strict', 'loose', 'disabled')
    assert pylint in ('enabled', 'disabled')

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

    if source == '__init__.py':
        mypy = 'disabled'

    if ctx.in_group(ctx.GRP_BUILD_TOOLS):
        mypy = 'disabled'
        pylint = 'disabled'

    if ctx.cmd == 'test' and {'all', 'lint', 'mypy'} & ctx.TEST_TAGS and mypy != 'disabled':
        with ctx.group(ctx.GRP_RUN_TESTS):
            task = run_mypy(env=ctx.env, strict=(mypy == 'strict'))
            task.set_inputs(target_node)
            ctx.add_to_group(task)

    if ctx.cmd == 'test' and {'all', 'lint', 'pylint'} & ctx.TEST_TAGS and pylint != 'disabled':
        with ctx.group(ctx.GRP_RUN_TESTS):
            task = run_pylint(env=ctx.env)
            task.set_inputs(target_node)
            ctx.add_to_group(task)

    return target_node


class run_py_test(Task):
    always_run = True

    def __init__(self, *, env, timeout=None):
        super().__init__(env=env)

        self.__timeout = timeout or 60
        assert self.__timeout > 0

    def __str__(self):
        return self.inputs[0].relpath()

    def keyword(self):
        return 'Testing'

    def run(self):
        ctx = self.generator.bld

        mod_path = self.inputs[0].relpath()
        assert mod_path.endswith('.py') or mod_path.endswith('.so')
        mod_name = '.'.join(os.path.splitext(mod_path)[0].split(os.sep))

        cmd = [
            ctx.env.PYTHON[0],
            '-m', 'noisidev.test_runner',
            '--store-result=%s' % os.path.join(ctx.TEST_RESULTS_PATH, mod_name),
            '--coverage=%s' % ('true' if ctx.options.coverage else 'false'),
            '--tags=%s' % ','.join(ctx.TEST_TAGS),
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
def add_py_test_runner(ctx, target, timeout=None):
    if ctx.cmd == 'test':
        with ctx.group(ctx.GRP_RUN_TESTS):
            task = run_py_test(env=ctx.env, timeout=timeout)
            task.set_inputs(target)
            ctx.add_to_group(task)


@conf
def py_test(ctx, source, mypy='loose', **kwargs):
    if not ctx.env.ENABLE_TEST:
        return

    with ctx.group(ctx.GRP_BUILD_TESTS):
        target = ctx.py_module(source, mypy=mypy)

    ctx.add_py_test_runner(target, **kwargs)
