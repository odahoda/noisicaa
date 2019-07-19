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
import sys

if sys.version_info < (3, 5):
    sys.stderr.write("At least python V3.5 required.\n")
    sys.exit(1)

if 'VIRTUAL_ENV' not in os.environ:
    venv_marker = '.venv'
    if os.path.isfile(venv_marker):
        venv_path = open(venv_marker, 'r').readline().strip()
        py_path = os.path.join(venv_path, 'bin', 'python')
        if os.path.isfile(py_path):
            os.environ['VIRTUAL_ENV'] = venv_path
            os.environ['LD_LIBRARY_PATH'] = os.path.join(venv_path, 'lib')
            os.environ['PATH'] = os.pathsep.join([os.path.join(venv_path, 'bin')] + os.environ.get('PATH', '').split(os.pathsep))
            argv = [py_path] + sys.argv
            os.execv(argv[0], argv)



import email.parser
import os.path
import py_compile
import re
import shutil
import sys
import urllib.parse

from waflib.Configure import conf
from waflib.Task import Task
from waflib.Context import BOTH, STDOUT
from waflib.Errors import WafError
from waflib.Logs import make_logger

top = '.'
out = 'build'

def options(ctx):
    ctx.load('virtenv', tooldir='build_utils/waf')
    ctx.load('compiler_cxx')
    ctx.load('compiler_c')


@conf
def pkg_config(ctx, store, package, minver):
    ctx.check_cfg(
        package=package,
        args=['%s >= %s' % (package, minver), '--cflags', '--libs'],
        uselib_store=store,
        pkg_config_path=os.path.join(
            ctx.env.VIRTUAL_ENV, 'lib', 'pkgconfig'))


def configure(ctx):
    # This one must come first, because it sets up the virtual environment where everything else
    # below should search for dependencies.
    ctx.load('virtenv', tooldir='build_utils/waf')

    ctx.load('compiler_cxx')
    ctx.load('compiler_c')
    ctx.load('python')
    ctx.load('local_rpath', tooldir='build_utils/waf')
    ctx.load('proto', tooldir='build_utils/waf')
    ctx.load('python', tooldir='build_utils/waf')
    ctx.load('cython', tooldir='build_utils/waf')
    ctx.load('model', tooldir='build_utils/waf')
    ctx.load('static', tooldir='build_utils/waf')
    ctx.load('csound', tooldir='build_utils/waf')
    ctx.load('sf2', tooldir='build_utils/waf')
    ctx.load('plugins', tooldir='build_utils/waf')
    ctx.load('svg', tooldir='build_utils/waf')
    ctx.load('faust', tooldir='build_utils/waf')

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

    old_grp = ctx.current_group
    ctx.set_group('buildtools')
    try:
        ctx.recurse('build_utils')
    finally:
        ctx.set_group(old_grp)

    ctx.recurse('noisicaa')
    ctx.recurse('data')

    old_grp = ctx.current_group
    ctx.set_group('tests')
    try:
        ctx.recurse('noisidev')
        ctx.recurse('testdata')
    finally:
        ctx.set_group(old_grp)
