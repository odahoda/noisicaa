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

import distutils.version
import contextlib
import glob
import os
import os.path
import sys

from waflib.Configure import conf
from waflib.Build import BuildContext


if sys.version_info < (3, 5):
    sys.stderr.write("At least python V3.5 required.\n")
    sys.exit(1)

if 'VIRTUAL_ENV' not in os.environ or 'LD_LIBRARY_PATH' not in os.environ:
    venv_marker = '.venv'
    if os.path.isfile(venv_marker):
        venv_path = open(venv_marker, 'r').readline().strip()
        py_path = os.path.join(venv_path, 'bin', 'python')
        if os.path.isfile(py_path):
            env = dict(os.environ)
            env['VIRTUAL_ENV'] = venv_path
            env['LD_LIBRARY_PATH'] = os.path.join(venv_path, 'lib')
            env['PATH'] = os.pathsep.join(
                [os.path.join(venv_path, 'bin')] + os.environ.get('PATH', '').split(os.pathsep))
            argv = [py_path] + sys.argv
            os.execve(argv[0], argv, env)


# Properly format command lines when using -v
os.environ['WAF_CMD_FORMAT'] = 'string'

top = '.'
out = 'build'

Version = distutils.version.LooseVersion


def options(ctx):
    ctx.load('build_utils.waf.virtenv', tooldir='.')
    ctx.load('build_utils.waf.test', tooldir='.')
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


@conf
@contextlib.contextmanager
def group(ctx, grp):
    old_grp = ctx.current_group
    ctx.set_group(grp)
    try:
        yield
    finally:
        ctx.set_group(old_grp)

@conf
def in_group(ctx, grp):
    return ctx.get_group_name(ctx.current_group) == grp


def configure(ctx):
    # This one must come first, because it sets up the virtual environment where everything else
    # below should search for dependencies.
    ctx.load('build_utils.waf.virtenv', tooldir='.')

    os_dist = ctx.env.OS_DIST
    os_release = Version(ctx.env.OS_RELEASE)

    ctx.load('compiler_cxx')
    ctx.load('compiler_c')
    ctx.load('python')
    ctx.load('build_utils.waf.install', tooldir='.')
    ctx.load('build_utils.waf.test', tooldir='.')
    ctx.load('build_utils.waf.local_rpath', tooldir='.')
    ctx.load('build_utils.waf.proto', tooldir='.')
    ctx.load('build_utils.waf.python', tooldir='.')
    ctx.load('build_utils.waf.cython', tooldir='.')
    ctx.load('build_utils.waf.model', tooldir='.')
    ctx.load('build_utils.waf.static', tooldir='.')
    ctx.load('build_utils.waf.csound', tooldir='.')
    ctx.load('build_utils.waf.sf2', tooldir='.')
    ctx.load('build_utils.waf.plugins', tooldir='.')
    ctx.load('build_utils.waf.svg', tooldir='.')
    ctx.load('build_utils.waf.faust', tooldir='.')

    ctx.check_python_version(minver=(3, 5))
    ctx.check_python_headers(features=['pyext'])

    ctx.pkg_config('GTK2', 'gtk+-2.0', '2.24')
    ctx.pkg_config('PROTOBUF', 'protobuf', '3.7')
    ctx.pkg_config('UNWIND', 'libunwind-generic', '1.1')
    ctx.pkg_config('SRATOM', 'sratom-0', '0.4')
    ctx.pkg_config('LILV', 'lilv-0', '0.22')
    ctx.pkg_config('SUIL', 'suil-0', '0.10.0')
    ctx.pkg_config('SNDFILE', 'sndfile', '1.0')
    ctx.pkg_config('FLUIDSYNTH', 'fluidsynth', '1.1.6')
    ctx.pkg_config('AVUTIL', 'libavutil', '54')
    ctx.pkg_config('SWRESAMPLE', 'libswresample', '1.2')
    ctx.pkg_config('PORTAUDIO', 'portaudio-2.0', '19')
    if os_dist == 'ubuntu' and os_release < Version('18.04'):
        # libgoogle-perftools-dev in xenial does not contain libprofiler.pc
        ctx.check(header_name='gperftools/profiler.h', features='cxx cxxprogram')
        ctx.check(lib='profiler', features='cxx cxxprogram')
    else:
        ctx.pkg_config('PROFILER', 'libprofiler', '2.4')

    ctx.env.LIB_CSOUND = ['csound64']
    ctx.env.CFLAGS_CSOUND = ['-DHAVE_PTHREAD_SPIN_LOCK']
    ctx.env.CXXFLAGS_CSOUND = ['-DHAVE_PTHREAD_SPIN_LOCK']

    ctx.env.append_value('CXXFLAGS', ['-g', '-O2', '-std=c++11', '-Wall', '-pedantic'])
    if os_dist == 'ubuntu' and os_release < Version('18.04'):
        # gcc on ubuntu xenial complains about unused variables in generated proto files.
        ctx.env.append_value('CXXFLAGS', ['-Wno-error=unused-variable'])
        # gcc on ubuntu xenial doesn't like some pointer arithmetics...
        ctx.env.append_value('CXXFLAGS', ['-Wno-error=strict-aliasing'])
    ctx.env.append_value('CFLAGS', ['-g', '-O2'])
    ctx.env.append_value('LIBPATH', [os.path.join(ctx.env.VIRTUAL_ENV, 'lib')])
    ctx.env.append_value('INCLUDES', [os.path.join(ctx.env.VIRTUAL_ENV, 'include')])

    ctx.env.DATADIR = os.path.join(ctx.env.PREFIX, 'share', 'noisicaa')
    ctx.env.LIBDIR = os.path.join(ctx.env.PREFIX, 'lib', 'noisicaa')

    ctx.write_config_header('config.h')


def build(ctx):
    ctx.init_test()

    ctx.GRP_BUILD_TOOLS = 'build:tools'
    ctx.GRP_BUILD_MAIN = 'build:main'
    ctx.GRP_BUILD_TESTS = 'build:tests'
    ctx.GRP_RUN_TESTS = 'run:tests'

    ctx.add_group(ctx.GRP_BUILD_TOOLS)
    ctx.add_group(ctx.GRP_BUILD_MAIN)
    ctx.add_group(ctx.GRP_BUILD_TESTS)
    ctx.add_group(ctx.GRP_RUN_TESTS)

    ctx.set_group(ctx.GRP_BUILD_MAIN)

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
        use=[])

    with ctx.group(ctx.GRP_BUILD_TOOLS):
        ctx.recurse('build_utils')

    ctx.recurse('noisicaa')
    ctx.recurse('misc')
    ctx.recurse('data')

    if ctx.env.ENABLE_TEST:
        with ctx.group(ctx.GRP_BUILD_TESTS):
            ctx.recurse('noisidev')
            ctx.recurse('testdata')

    for lib in ['libprotobuf', 'libcsound64', 'liblilv-0', 'libsuil-0']:
        for path in glob.glob(os.path.join(ctx.env.VIRTUAL_ENV, 'lib', lib + '.so*')):
            if os.path.islink(path):
                ctx.symlink_as(
                    os.path.join(ctx.env.LIBDIR, os.path.basename(path)),
                    os.path.basename(os.path.realpath(path)))
            else:
                ctx.install_files(
                    ctx.env.LIBDIR,
                    ctx.root.make_node(path))

    ctx.install_post_func()


class TestContext(BuildContext):
    """run unittests"""

    cmd = 'test'
