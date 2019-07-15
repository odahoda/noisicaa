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

from waflib.Configure import conf
from waflib.Task import Task

top = '.'
out = 'build'


def options(ctx):
    ctx.load('compiler_cxx')
    ctx.load('compiler_c')
    ctx.load('python')


@conf
def pkg_config(ctx, store, package, minver):
    ctx.check_cfg(
        package=package,
        args=['%s >= %s' % (package, minver), '--cflags', '--libs'],
        uselib_store=store,
        pkg_config_path=os.path.join(
            ctx.env.VIRTUAL_ENV, 'lib', 'pkgconfig'))


def configure(ctx):
    if 'VIRTUAL_ENV' not in os.environ:
        ctx.fatal("Not running in a virtual env.")

    ctx.env.VIRTUAL_ENV = os.environ['VIRTUAL_ENV']

    ctx.load('compiler_cxx')
    ctx.load('compiler_c')
    ctx.load('python')
    ctx.load('local_rpath', tooldir='waftools')
    ctx.load('proto', tooldir='waftools')
    ctx.load('python', tooldir='waftools')
    ctx.load('cython', tooldir='waftools')
    ctx.load('model', tooldir='waftools')
    ctx.load('static', tooldir='waftools')
    ctx.load('csound', tooldir='waftools')
    ctx.load('sf2', tooldir='waftools')
    ctx.load('plugins', tooldir='waftools')
    ctx.load('svg', tooldir='waftools')
    ctx.load('faust', tooldir='waftools')

    ctx.check_python_version(minver=(3, 5))
    ctx.check_python_headers(features=['pyext'])

    ctx.pkg_config('GTK2', 'gtk+-2.0', '2.24')
    ctx.pkg_config('PROTOBUF', 'protobuf', '3.7')
    ctx.pkg_config('UNWIND', 'libunwind-generic', '1.1')
    ctx.pkg_config('SRATOM', 'sratom-0', '0.6')
    ctx.pkg_config('LILV', 'lilv-0', '0.22')
    ctx.pkg_config('SUIL', 'suil-0', '0.10.0')
    ctx.pkg_config('SNDFILE', 'sndfile', '1.0')
    ctx.pkg_config('FLUIDSYNTH', 'fluidsynth', '1.1.6')
    ctx.pkg_config('AVUTIL', 'libavutil', '55')
    ctx.pkg_config('SWRESAMPLE', 'libswresample', '2.9')
    ctx.pkg_config('PORTAUDIO', 'portaudio-2.0', '19')
    ctx.pkg_config('PROFILER', 'libprofiler', '2.5')

    ctx.env.LIB_CSOUND = ['csound64']

    ctx.env.append_value('CXXFLAGS', ['-g', '-O2', '-std=c++11'])
    ctx.env.append_value('CFLAGS', ['-g', '-O2'])
    ctx.env.append_value('LIBPATH', [os.path.join(ctx.env.VIRTUAL_ENV, 'lib')])
    ctx.env.append_value('INCLUDES', [os.path.join(ctx.env.VIRTUAL_ENV, 'include')])


def build(ctx):
    ctx.add_group('buildtools')
    ctx.add_group('noisicaa')
    ctx.add_group('tests')

    ctx.set_group('noisicaa')

    # A dummy library with the common include dirs, etc.
    # noisicaä libraries should use this lib to pull in those settings.
    ctx(name='NOISELIB',
        export_includes=[
            ctx.srcnode,
            ctx.bldnode,
        ],
        export_lib=[
            'pthread',
        ],
        use=[],
    )

    ctx.recurse('noisidev')
    ctx.recurse('noisicaa')
    ctx.recurse('data')
    ctx.recurse('testdata')
