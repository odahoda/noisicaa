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
import json
import operator
import os
import os.path
import re
import shutil
import subprocess
import venv

from waflib.Configure import conf
from waflib.Errors import ConfigurationError, WafError
from waflib.Context import BOTH, STDOUT


Version = distutils.version.LooseVersion


DEFAULT_VENVDIR = os.path.expanduser('~/.local/share/virtualenvs/noisicaa')


def options(ctx):
    grp = ctx.add_option_group('Virtual Environment options')
    grp.add_option('--venvdir', action='store', default=None, help='Where to setup the virtual environment [default: %s]' % DEFAULT_VENVDIR)
    grp.add_option('--download', action='store_true', default=False, help='Download and install missing packages into virtual environment')
    grp.add_option('--install-system-packages', action='store_true', default=False, help='Download and install missing system package (requires `sudo` priviledge)')
    grp.add_option('--os-dist', default=False, help='Override the auto detected OS distribution (format "${name}:${release}", e.g. "ubuntu:18.10")')


def configure(ctx):
    ctx.check_virtual_env()

    ctx.find_program('lsb_release')

    if ctx.options.install_system_packages:
        # Prefer x11-ssh-askpass over the default ssh-askpass. The latter might point to ksshaskpass,
        # which might not play well with sudo
        # (https://bugs.launchpad.net/ubuntu/+source/ksshaskpass/+bug/1728696).
        ctx.find_program('x11-ssh-askpass', var='SSH_ASKPASS', mandatory=False, path_list='/usr/lib/ssh')
        if not ctx.env.SSH_ASKPASS:
            ctx.find_program('ssh-askpass', var='SSH_ASKPASS', mandatory=False)

    if ctx.options.os_dist:
        os_dist, os_release = ctx.options.os_dist.split(':', 1)
        os_release = Version(os_release)
    else:
        ctx.start_msg("Detect OS distribution")
        out = ctx.cmd_and_log(['/usr/bin/lsb_release', '-s', '-i', '-r'], output=STDOUT)
        os_dist, os_release = [s.strip() for s in out.lower().split('\n', 1)]
        os_release = Version(os_release)
        ctx.end_msg("%s %s" % (os_dist, os_release))

    ctx.start_msg("Query pip for installed packages")
    pip_mgr = PipManager(ctx)
    pip_mgr.update_packages()
    ctx.to_log('Installed pip packages:')
    for name, version in pip_mgr.packages:
        ctx.to_log('  %s: %s' % (name, version))
    ctx.end_msg("ok")

    if os_dist == 'ubuntu':
        ctx.start_msg("Query dpkg for installed packages")
        sys_mgr = DebManager(ctx)
        sys_mgr.update_packages()
        ctx.to_log('Installed system packages:')
        for name, version in sys_mgr.packages:
            ctx.to_log('  %s: %s' % (name, version))
        ctx.end_msg("ok")
    else:
        ctx.to_log("Unsupported distribution. Can't install system packages.")
        if ctx.options.install_system_packages:
            ctx.fatal("Installing system packages is not supported for distribution '%s'" % os_dist)
        sys_mgr = UnsupportedDistManager(ctx)

    ### Basic venv stuff:
    pip_mgr.check_package('pip', version='>=19.0')
    pip_mgr.check_package('setuptools', version='>=41.0')
    pip_mgr.check_package('wheel', version='>=0.33')

    ### Runtime dependencies:

    # csound
    if os_dist == 'ubuntu' and os_release >= Version('17.10'):
        sys_mgr.check_package('csound', version='>=1:6.08')
        sys_mgr.check_package('libcsound64-dev', version='>=1:6.08')
    else:
        # TODO: install this directly, not via PIP
        sys_mgr.check_package('libsamplerate0-dev')
        sys_mgr.check_package('libboost-dev')
        sys_mgr.check_package('flex')
        sys_mgr.check_package('bison')
        pip_mgr.check_package('csound', source='./3rdparty/csound/')

    # TODO: 'ubuntu', '<17.10')
    # TODO: install this directly, not via PIP
    #pip_mgr.check_package('lv2', source='./3rdparty/lv2/')
    # TODO: install this directly, not via PIP
    pip_mgr.check_package('lilv', source='./3rdparty/lilv/')
    # TODO: install this directly, not via PIP
    pip_mgr.check_package('suil', source='./3rdparty/suil/')
    pip_mgr.check_package('PyGObject')
    pip_mgr.check_package('PyQt5')
    pip_mgr.check_package('eventfd')
    pip_mgr.check_package('gbulb')
    pip_mgr.check_package('lucky-humanize')
    pip_mgr.check_package('numpy')
    pip_mgr.check_package('portalocker')
    pip_mgr.check_package('posix-ipc')
    pip_mgr.check_package('protobuf', version='3.7.1')
    pip_mgr.check_package('psutil')
    pip_mgr.check_package('PyAudio')
    pip_mgr.check_package('pyparsing')
    # TODO: get my changes upstream and use regular quamash package from pip.
    pip_mgr.check_package('Quamash', source='git+https://github.com/odahoda/quamash.git#egg=quamash')
    pip_mgr.check_package('sortedcontainers')
    pip_mgr.check_package('toposort')
    pip_mgr.check_package('urwid')

    # sf2
    sys_mgr.check_package('libfluidsynth1')
    sys_mgr.check_package('timgm6mb-soundfont')
    sys_mgr.check_package('fluid-soundfont-gs')
    sys_mgr.check_package('fluid-soundfont-gm')

    # encoding
    sys_mgr.check_package('ffmpeg')

    sys_mgr.check_package('libgoogle-perftools4')

    # Build dependencies
    # TODO: install those directly, not via PIP
    pip_mgr.check_package('protoc', source='./3rdparty/protoc/')
    pip_mgr.check_package('faust', source='./3rdparty/faust/')
    pip_mgr.check_package('faustlibraries', source='./3rdparty/faustlibraries/')
    pip_mgr.check_package('cssutils')
    pip_mgr.check_package('Cython', version='0.29.6')
    pip_mgr.check_package('Jinja2')
    pip_mgr.check_package('pkgconfig')
    pip_mgr.check_package('PyYAML')
    # TODO: get my changes upstream and use regular mypy-protobuf package from pip.
    pip_mgr.check_package('mypy-protobuf', source='git+https://github.com/odahoda/mypy-protobuf.git#egg=mypy-protobuf&subdirectory=python')

    # qt4
    sys_mgr.check_package('libqt4-dev')

    # gtk2
    sys_mgr.check_package('libgtk2.0-dev')
    sys_mgr.check_package('libgirepository1.0-dev')

    # lv2/lilv
    sys_mgr.check_package('libserd-dev')
    sys_mgr.check_package('libsord-dev')
    sys_mgr.check_package('libsratom-dev')
    if os_dist == 'ubuntu' and os_release >= Version('17.10'):
        sys_mgr.check_package('lv2-dev')

    # ladspa
    sys_mgr.check_package('ladspa-sdk')

    # sndfile
    sys_mgr.check_package('libsndfile1-dev')

    # protocol buffers
    sys_mgr.check_package('autoconf')
    sys_mgr.check_package('automake')
    sys_mgr.check_package('libtool')
    sys_mgr.check_package('curl')
    sys_mgr.check_package('make')
    sys_mgr.check_package('g++')
    sys_mgr.check_package('unzip')

    # libswresample
    sys_mgr.check_package('libswresample-dev')

    # libavutil
    sys_mgr.check_package('libavutil-dev')

    # profiling
    sys_mgr.check_package('libgoogle-perftools-dev')

    # other...
    sys_mgr.check_package('cmake')
    sys_mgr.check_package('python3-dev')
    sys_mgr.check_package('portaudio19-dev')
    sys_mgr.check_package('libfluidsynth-dev')
    sys_mgr.check_package('inkscape')
    sys_mgr.check_package('zlib1g-dev')
    sys_mgr.check_package('libunwind-dev')

    # Dev dependencies
    pip_mgr.check_package('asynctest')
    pip_mgr.check_package('async-generator')
    pip_mgr.check_package('coverage')
    pip_mgr.check_package('mox3')
    pip_mgr.check_package('py-cpuinfo')
    pip_mgr.check_package('pyfakefs')
    pip_mgr.check_package('pylint', version='2.3.1')
    pip_mgr.check_package('mypy', version='0.701')
    pip_mgr.check_package('mypy-extensions')
    pip_mgr.check_package('PyGObject-stubs')

    # For indicator-cpufreq
    pip_mgr.check_package('dbus-python')
    sys_mgr.check_package('bzr')
    pip_mgr.check_package('python-distutils-extra', source='bzr+lp:python-distutils-extra#egg=python-distutils-extra')
    pip_mgr.check_package('indicator-cpufreq', source='bzr+lp:indicator-cpufreq#egg=indicator-cpufreq')
    sys_mgr.check_package('indicator-cpufreq')

    sys_mgr.check_package('mda-lv2')
    sys_mgr.check_package('swh-plugins')
    sys_mgr.check_package('gdb')
    sys_mgr.check_package('xvfb')
    sys_mgr.check_package('google-perftools')
    sys_mgr.check_package('intltool')

    # VMtest dependencies:
    pip_mgr.check_package('paramiko')
    pip_mgr.check_package('python-xlib')
    sys_mgr.check_package('virtualbox')

@conf
def check_virtual_env(ctx):
    ctx.start_msg('Checking for virtual environment')

    venvdir = os.environ.get('VIRTUAL_ENV', None)
    if not venvdir and os.path.isfile('.venv'):
        venvdir = open('.venv', 'r').readline().strip()

    if not venvdir:
        venvdir = ctx.options.venvdir

    if not venvdir:
        venvdir = DEFAULT_VENVDIR

    ctx.to_log("Using virtual env path %s" % venvdir)

    py_path = os.path.join(venvdir, 'bin', 'python')
    if not os.path.isfile(py_path):
        ctx.to_log("No virtual environment found, creating...")
        try:
            env_builder = venv.EnvBuilder(
                system_site_packages=False,
                with_pip=True)
            env_builder.create(venvdir)
        except Exception as exc:
            shutil.rmtree(venvdir)
            ctx.fatal("Failed to create virtual env: %s" % exc)
        ctx.to_log("  ok.")

    old_venvdir = None
    if os.path.isfile('.venv'):
        old_venvdir = open('.venv', 'r').readline().strip()

    if venvdir != old_venvdir:
        ctx.to_log("Creating .venv sentinel file...")
        with open('.venv', 'w') as fp:
            fp.write(venvdir)
            fp.write('\n')
        ctx.to_log("  ok.")

    ctx.env.VIRTUAL_ENV = venvdir
    ctx.environ['PATH'] = os.pathsep.join([os.path.join(venvdir, 'bin')] + ctx.environ.get('PATH', '').split(os.pathsep))

    os.environ['VIRTUAL_ENV'] = venvdir
    os.environ['LD_LIBRARY_PATH'] = os.path.join(venvdir, 'lib')
    os.environ['PATH'] = os.pathsep.join([os.path.join(venvdir, 'bin')] + os.environ.get('PATH', '').split(os.pathsep))

    ctx.end_msg(venvdir)


class PackageManager(object):
    def __init__(self, ctx):
        self._ctx = ctx
        self._packages = {}

    @property
    def packages(self):
        return sorted(self._packages.items())

    def is_installed(self, pkg):
        return pkg in self._packages

    def version(self, pkg):
        return self._packages[pkg]

    def split_spec(self, spec):
        if spec.startswith('<=') or spec.startswith('>=') or spec.startswith('=='):
            return spec[:2], spec[2:]

        if spec.startswith('<') or spec.startswith('>'):
            return spec[:1], spec[1:]

        return '==', spec

    def check_version(self, pkg, expected_spec):
        have = self.version(pkg)
        op, version = self.split_spec(expected_spec)
        return self.compare_versions(self.version(pkg), op, version)

    def compare_versions(self, v1, op, v2):
        raise NotImplementedError

    def update_packages(self):
        raise NotImplementedError

    def install_package(self, name, version=None, source=None):
        raise NotImplementedError

    def check_package(self, name, version, source, allow_install):
        need_install = False
        if not self.is_installed(name):
            self._ctx.to_log("Package is not installed")
            need_install = True

        else:
            self._ctx.to_log("Found installed version %s" % self.version(name))
            if version and not self.check_version(name, version):
                self._ctx.to_log("Requirement '%s' not met, requires update" % version)
                need_install = True

        if need_install:
            if not allow_install:
                self._ctx.to_log("Not installing system package myself.")
                self._ctx.fatal("missing")

            try:
                self.install_package(name, version, source)
            except WafError as exc:
                self._ctx.fatal("Failed to install pip package '%s'" % name)

            self.update_packages()
            assert not version or self.check_version(name, version)


class PipManager(PackageManager):
    def __init__(self, ctx):
        super().__init__(ctx)

        self.__pip_path = os.path.join(self._ctx.env.VIRTUAL_ENV, 'bin', 'pip')
        self.__pip_cmd = [self.__pip_path, '--disable-pip-version-check']

    def compare_versions(self, v1, op_name, v2):
        op = {
            '<=': operator.le,
            '>=': operator.ge,
            '<': operator.lt,
            '>': operator.gt,
            '==': operator.eq,
        }[op_name]
        return op(Version(v1), Version(v2))

    def update_packages(self):
        p = subprocess.run(self.__pip_cmd + ['list', '--format=json'], stdout=subprocess.PIPE, check=True)
        self._packages = {p['name']: p['version'] for p in json.loads(p.stdout)}

    def install_package(self, name, version=None, source=None):
        if source:
            spec = source
        else:
            spec = name
            if version:
                op, version = self.split_spec(version)
                spec += op
                spec += version
        self._ctx.cmd_and_log(self.__pip_cmd + ['install', '-U', spec], output=BOTH)

    def check_package(self, name, version=None, source=None):
        self._ctx.start_msg("Checking pip package '%s'" % name)
        super().check_package(name, version, source, self._ctx.options.download)
        self._ctx.end_msg(self.version(name))


class DebManager(PackageManager):
    def __init__(self, ctx):
        super().__init__(ctx)

    def compare_versions(self, v1, op_name, v2):
        op = {
            '<=': 'le',
            '>=': 'ge',
            '<': 'lt',
            '>': 'gt',
            '==': 'eq',
        }[op_name]

        p = subprocess.run(['/usr/bin/dpkg', '--compare-versions', v1, op, v2])
        return p.returncode == 0

    def update_packages(self):
        p = subprocess.run(['/usr/bin/dpkg-query', '--show', '--showformat', '${Package}\t${Version}\n'], stdout=subprocess.PIPE, check=True)

        self._packages.clear()
        for l in p.stdout.splitlines():
            l = l.decode('utf-8')
            pkg, version = l.split('\t')
            self._packages[pkg] = version

    def install_package(self, name, version=None, source=None):
        env = dict(os.environ)
        cmd = ['/usr/bin/sudo']
        if self._ctx.env.SSH_ASKPASS:
            env['SUDO_ASKPASS'] = self._ctx.env.SSH_ASKPASS[0]
            cmd += ['--askpass']
        else:
            cmd += ['--non-interactive']
        cmd += ['--', '/usr/bin/apt-get', 'install', name]

        self._ctx.cmd_and_log(cmd, output=BOTH, env=env)

    def check_package(self, name, version=None):
        self._ctx.start_msg("Checking system package '%s'" % name)
        super().check_package(name, version, None, self._ctx.options.install_system_packages)
        self._ctx.end_msg(self.version(name))


class UnsupportedDistManager(PackageManager):
    def check_package(self, name, version=None):
        pass
