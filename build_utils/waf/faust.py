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

from waflib.Configure import conf


def build_dsp(task):
    ctx = task.generator.bld
    cmd = [
        'bin/build-faust-processor',
        task.generator.cls_name,
        task.inputs[0].abspath(),
        task.outputs[0].parent.abspath(),
    ]
    task.exec_command(cmd, cwd=ctx.top_dir)


@conf
def faust_dsp(ctx, cls_name, source='processor.dsp'):
    source = ctx.path.make_node(source)
    ctx(rule=build_dsp,
        source=[source],
        target=[
            source.change_ext('.cpp'),
            source.change_ext('.h'),
            source.change_ext('.json'),
        ],
        cls_name=cls_name)

    ctx.shlib(
        target='noisicaa-builtin_nodes-%s-processor' % cls_name.lower(),
        source='processor.cpp',
        use=[
            'NOISELIB',
            'noisicaa-audioproc-public',
            'noisicaa-host_system',
        ],
    )
