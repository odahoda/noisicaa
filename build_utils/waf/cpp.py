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

import os
import os.path
import subprocess
import sys

from waflib.Configure import conf
from waflib.Task import Task
from waflib import Utils


def configure(ctx):
    if ctx.env.ENABLE_TEST:
        ctx.find_program('clang-tidy-8', var='CLANG_TIDY', mandatory=False)



class run_clang_tidy(Task):
    always_run = True

    def __str__(self):
        return self.inputs[0].relpath()

    def keyword(self):
        return 'Lint (clang-tidy)'

    @property
    def mod_name(self):
        mod_path = self.inputs[0].relpath()
        assert mod_path.endswith('.cpp')
        return '.'.join(os.path.splitext(mod_path)[0].split(os.sep))

    @property
    def test_id(self):
        return self.mod_name + ':clang-tidy'

    def run(self):
        ctx = self.generator.bld

        success = True
        try:
            argv = [
                ctx.env.CLANG_TIDY[0],
                '-quiet',
                self.inputs[0].relpath(),
                '--',
                '-Wall',
                '-I.', '-Ibuild',
            ]
            argv += ['-I%s' % p for p in ctx.env.INCLUDES_LILV]
            argv += ['-I%s' % p for p in ctx.env.INCLUDES_SUIL]
            argv += ['-I%s' % p for p in ctx.env.INCLUDES_GTK2]
            argv += ['-I%s' % p for p in ctx.env.INCLUDES]

            env = dict(os.environ)

            kw = {
                'cwd': ctx.top_dir,
                'env': env,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
            }

            ctx.log_command(argv, kw)
            _, out, _ = Utils.run_process(argv, kw)
            out = out.strip()

            if out:
                success = False

            out_path = os.path.join(ctx.TEST_RESULTS_PATH, self.mod_name, 'clang-tidy.log')
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'wb') as fp:
                fp.write(out)

            if out and ctx.options.fail_fast:
                sys.stderr.write(out.decode('utf-8'))
                sys.stderr.write('\n')
                raise RuntimeError("clang-tidy for %s failed." % self.mod_name)

        except Exception:
            success = False
            raise

        finally:
            ctx.record_test_state(self.test_id, success)


@conf
def cpp_module(ctx, source, **kwargs):
    assert source.endswith('.cpp')

    source_node = ctx.path.make_node(source)

    if (ctx.cmd == 'test'
            and ctx.env.CLANG_TIDY
            and ctx.should_run_test(source_node)
            and {'all', 'lint', 'clang-tidy'} & ctx.TEST_TAGS):
        with ctx.group(ctx.GRP_RUN_TESTS):
            task = run_clang_tidy(env=ctx.env)
            task.set_inputs(source_node)
            if not ctx.options.only_failed or not ctx.get_test_state(task.test_id):
                ctx.add_to_group(task)

    return source_node
