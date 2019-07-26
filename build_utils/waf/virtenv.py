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
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import venv
import zipfile

from waflib.Configure import conf
from waflib.Context import BOTH, STDOUT


Version = distutils.version.LooseVersion


DEFAULT_VENVDIR = 'venv'

RUNTIME = 1
BUILD = 2
DEV = 3
VMTEST = 4


def options(ctx):
    grp = ctx.add_option_group('Virtual Environment options')
    grp.add_option(
        '--venvdir',
        action='store',
        default=None,
        help='Where to setup the virtual environment [default: %s]' % DEFAULT_VENVDIR)
    grp.add_option(
        '--download',
        action='store_true',
        default=False,
        help='Download and install missing packages into virtual environment')
    grp.add_option(
        '--install-system-packages',
        action='store_true',
        default=False,
        help='Download and install missing system package (requires `sudo` priviledge)')
    grp.add_option(
        '--os-dist',
        default=False,
        help=('Override the auto detected OS distribution (format "${name}:${release}",'
              ' e.g. "ubuntu:18.10")'))
    grp.add_option(
        '--enable-tests',
        action='store_true',
        default=False,
        help='Build test cases')
    grp.add_option(
        '--enable-vmtests',
        action='store_true',
        default=False,
        help='Build VM test cases (implies --enable-test)')


def configure(ctx):
    ctx.check_virtual_env()

    ctx.start_msg("Build with tests")
    if ctx.options.enable_tests or ctx.options.enable_vmtests:
        ctx.env.ENABLE_TEST = True
    ctx.end_msg("Yes" if ctx.env.ENABLE_TEST else "No")

    ctx.start_msg("Build with VM tests")
    if ctx.options.enable_vmtests:
        ctx.env.ENABLE_VMTEST = True
    ctx.end_msg("Yes" if ctx.env.ENABLE_TEST else "No")

    ctx.find_program('lsb_release')

    if ctx.options.install_system_packages:
        # Prefer x11-ssh-askpass over the default ssh-askpass. The latter might point to
        # ksshaskpass, which might not play well with sudo
        # (https://bugs.launchpad.net/ubuntu/+source/ksshaskpass/+bug/1728696).
        ctx.find_program(
            'x11-ssh-askpass', var='SSH_ASKPASS', mandatory=False, path_list='/usr/lib/ssh')
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

    # Yes, some of these lines are very long, but let's stay consistent.
    # pylint: disable=line-too-long

    # Basic venv stuff:
    pip_mgr.check_package(BUILD, 'pip', version='>=19.0')
    pip_mgr.check_package(BUILD, 'setuptools', version='>=41.0')
    pip_mgr.check_package(BUILD, 'wheel', version='>=0.33')
    sys_mgr.check_package(BUILD, 'build-essential')
    sys_mgr.check_package(BUILD, 'python3-dev')

    # Misc pip packages:
    pip_mgr.check_package(RUNTIME, 'eventfd')
    pip_mgr.check_package(RUNTIME, 'lucky-humanize')
    pip_mgr.check_package(RUNTIME, 'numpy')
    pip_mgr.check_package(RUNTIME, 'portalocker')
    pip_mgr.check_package(RUNTIME, 'posix-ipc')
    pip_mgr.check_package(RUNTIME, 'psutil')
    pip_mgr.check_package(RUNTIME, 'pyparsing')
    pip_mgr.check_package(RUNTIME, 'sortedcontainers')
    pip_mgr.check_package(RUNTIME, 'toposort')
    pip_mgr.check_package(RUNTIME, 'urwid')
    pip_mgr.check_package(BUILD, 'cssutils')
    pip_mgr.check_package(BUILD, 'Cython', version='0.29.6')
    pip_mgr.check_package(BUILD, 'Jinja2')
    pip_mgr.check_package(BUILD, 'PyYAML')
    pip_mgr.check_package(BUILD, 'packaging', version='>=19.0')
    pip_mgr.check_package(BUILD, 'xunitparser')
    pip_mgr.check_package(DEV, 'asynctest')
    pip_mgr.check_package(DEV, 'async-generator')
    pip_mgr.check_package(DEV, 'coverage')
    pip_mgr.check_package(DEV, 'mox3')
    pip_mgr.check_package(DEV, 'py-cpuinfo')
    pip_mgr.check_package(DEV, 'pyfakefs')
    pip_mgr.check_package(DEV, 'pylint', version='2.3.1')
    pip_mgr.check_package(DEV, 'unittest-xml-reporting')

    # misc sys packages:
    sys_mgr.check_package(RUNTIME, 'ffmpeg')
    sys_mgr.check_package(RUNTIME, 'libxkbcommon-x11-0')
    sys_mgr.check_package(BUILD, 'cmake')
    sys_mgr.check_package(BUILD, 'python3-dev')
    sys_mgr.check_package(BUILD, 'portaudio19-dev')
    sys_mgr.check_package(BUILD, 'libfluidsynth-dev')
    sys_mgr.check_package(BUILD, 'inkscape')
    sys_mgr.check_package(BUILD, 'zlib1g-dev')
    sys_mgr.check_package(BUILD, 'libunwind-dev')
    sys_mgr.check_package(DEV, 'gdb')
    sys_mgr.check_package(DEV, 'xvfb')
    sys_mgr.check_package(DEV, 'intltool')

    # mypy
    pip_mgr.check_package(DEV, 'mypy', version='0.720')
    pip_mgr.check_package(RUNTIME, 'mypy-extensions')

    # sndfile
    sys_mgr.check_package(BUILD, 'libsndfile1-dev')

    # csound
    sys_mgr.check_package(BUILD, 'libsamplerate0-dev')
    sys_mgr.check_package(BUILD, 'libboost-dev')
    sys_mgr.check_package(BUILD, 'flex')
    sys_mgr.check_package(BUILD, 'bison')
    CSoundBuilder(ctx).check(RUNTIME, version='6.08.0')

    # LV2
    sys_mgr.check_package(BUILD, 'libserd-dev')
    sys_mgr.check_package(BUILD, 'libsord-dev')
    sys_mgr.check_package(BUILD, 'libsratom-dev')
    if os_dist == 'ubuntu' and os_release >= Version('17.10'):
        sys_mgr.check_package(BUILD, 'lv2-dev')
    else:
        LV2Builder(ctx).check(RUNTIME, version='1.14.0')
    LilvBuilder(ctx).check(RUNTIME, version='0.24.3-git')
    SuilBuilder(ctx).check(RUNTIME, version='0.10.0')
    sys_mgr.check_package(DEV, 'mda-lv2')

    # ladspa
    sys_mgr.check_package(BUILD, 'ladspa-sdk')
    sys_mgr.check_package(DEV, 'swh-plugins')

    # Faust
    FaustBuilder(ctx).check(BUILD, version='2.15.11')
    FaustLibrariesBuilder(ctx).check(BUILD, version='64a57f56')  # snapshot from 2019-03-30

    # libswresample
    sys_mgr.check_package(BUILD, 'libswresample-dev')

    # libavutil
    sys_mgr.check_package(BUILD, 'libavutil-dev')

    # sf2
    sys_mgr.check_package(RUNTIME, 'libfluidsynth1')
    sys_mgr.check_package(RUNTIME, 'timgm6mb-soundfont')
    sys_mgr.check_package(RUNTIME, 'fluid-soundfont-gs')
    sys_mgr.check_package(RUNTIME, 'fluid-soundfont-gm')

    # Qt
    pip_mgr.check_package(RUNTIME, 'PyQt5')
    # TODO: get my changes upstream and use regular quamash package from pip.
    pip_mgr.check_package(RUNTIME, 'Quamash', source='git+https://github.com/odahoda/quamash.git#egg=quamash')
    sys_mgr.check_package(BUILD, 'libqt4-dev')

    # GTK
    sys_mgr.check_package(BUILD, 'libgtk2.0-dev')
    sys_mgr.check_package(BUILD, 'libgirepository1.0-dev')
    pip_mgr.check_package(RUNTIME, 'PyGObject')
    pip_mgr.check_package(DEV, 'PyGObject-stubs')
    pip_mgr.check_package(RUNTIME, 'gbulb')

    # Protobuf
    pip_mgr.check_package(RUNTIME, 'protobuf', version='3.7.1')
    sys_mgr.check_package(BUILD, 'autoconf')
    sys_mgr.check_package(BUILD, 'automake')
    sys_mgr.check_package(BUILD, 'libtool')
    sys_mgr.check_package(BUILD, 'curl')
    sys_mgr.check_package(BUILD, 'make')
    sys_mgr.check_package(BUILD, 'g++')
    sys_mgr.check_package(BUILD, 'unzip')
    ProtocBuilder(ctx).check(BUILD, version='3.7.1')
    # TODO: get my changes upstream and use regular mypy-protobuf package from pip.
    pip_mgr.check_package(BUILD, 'mypy-protobuf', source='git+https://github.com/odahoda/mypy-protobuf.git#egg=mypy-protobuf&subdirectory=python')

    # profiling
    sys_mgr.check_package(RUNTIME, 'google-perftools')
    sys_mgr.check_package(RUNTIME, 'libgoogle-perftools4')
    sys_mgr.check_package(BUILD, 'libgoogle-perftools-dev')

    # indicator-cpufreq
    sys_mgr.check_package(DEV, 'libdbus-1-dev')
    pip_mgr.check_package(DEV, 'dbus-python')
    sys_mgr.check_package(DEV, 'bzr')
    pip_mgr.check_package(DEV, 'python-distutils-extra', source='bzr+lp:python-distutils-extra#egg=python-distutils-extra')
    pip_mgr.check_package(DEV, 'indicator-cpufreq', source='bzr+lp:indicator-cpufreq#egg=indicator-cpufreq')
    sys_mgr.check_package(DEV, 'indicator-cpufreq')

    # vmtest
    pip_mgr.check_package(VMTEST, 'paramiko')
    pip_mgr.check_package(VMTEST, 'python-xlib')
    sys_mgr.check_package(VMTEST, 'virtualbox')

    # pylint: enable=line-too-long

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

    venvdir = os.path.abspath(venvdir)

    ctx.to_log("Using virtual env path %s" % venvdir)

    py_path = os.path.join(venvdir, 'bin', 'python')
    if not os.path.isfile(py_path):
        ctx.to_log("No virtual environment found, creating...")
        try:
            env_builder = venv.EnvBuilder(
                system_site_packages=False,
                with_pip=True)
            env_builder.create(venvdir)
        except Exception as exc:  # pylint: disable=broad-except
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
    ctx.env.PYTHON = [os.path.join(venvdir, 'bin', 'python')]
    ctx.environ['PATH'] = os.pathsep.join(
        [os.path.join(venvdir, 'bin')] + ctx.environ.get('PATH', '').split(os.pathsep))

    os.environ['VIRTUAL_ENV'] = venvdir
    os.environ['LD_LIBRARY_PATH'] = os.path.join(venvdir, 'lib')
    os.environ['PATH'] = os.pathsep.join(
        [os.path.join(venvdir, 'bin')] + os.environ.get('PATH', '').split(os.pathsep))

    # Make sure the site-packages from the venv are visible, even on the initial run of waf, when
    # the venv didn't exist yet when it was started.
    site_packages_path = os.path.join(
        ctx.env.VIRTUAL_ENV, 'lib',
        'python%d.%d' % (sys.version_info[0], sys.version_info[1]), 'site-packages')
    sys.path.insert(0, site_packages_path)

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
        op, version = self.split_spec(expected_spec)
        return self.compare_versions(self.version(pkg), op, version)

    def compare_versions(self, v1, op, v2):
        raise NotImplementedError

    def update_packages(self):
        raise NotImplementedError

    def install_package(self, name, version=None, source=None):
        raise NotImplementedError

    def check_package(self, dep_type, name, version, source, message, allow_install):
        if dep_type >= DEV and not self._ctx.env.ENABLE_TEST:
            return
        if dep_type >= VMTEST and not self._ctx.env.ENABLE_VMTEST:
            return

        self._ctx.start_msg(message)

        need_install = False
        if not self.is_installed(name):
            self._ctx.to_log("Package is not installed")
            need_install = True
            self._ctx.end_msg("not found", 'YELLOW')

        else:
            self._ctx.to_log("Found installed version %s" % self.version(name))
            if version and not self.check_version(name, version):
                self._ctx.end_msg(self.version(name), 'YELLOW')
                self._ctx.to_log("Requirement '%s' not met, requires update" % version)
                need_install = True

        if need_install:
            if not allow_install:
                self._ctx.to_log("Not installing system package myself.")
                self._ctx.fatal("missing")

            if version:
                self._ctx.start_msg("Install '%s' (%s)" % (name, version))
            else:
                self._ctx.start_msg("Install '%s'" % name)

            self.install_package(name, version, source)
            self.update_packages()
            assert not version or self.check_version(name, version)

        self._ctx.end_msg(self.version(name))


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
        p = subprocess.run(
            self.__pip_cmd + ['list', '--format=json'],
            stdout=subprocess.PIPE, check=True)
        self._packages = {p['name']: p['version'] for p in json.loads(p.stdout.decode('utf-8'))}

    def get_pip_spec(self, name, version=None, source=None):
        if source:
            spec = source
        else:
            spec = name
            if version:
                op, version = self.split_spec(version)
                spec += op
                spec += version
        return spec

    def install_package(self, name, version=None, source=None):
        self._ctx.cmd_and_log(
            self.__pip_cmd + ['install', '-U', self.get_pip_spec(name, version, source)],
            output=BOTH)

    def check_package(self, dep_type, name, version=None, source=None):
        super().check_package(
            dep_type, name, version, source,
            "Checking pip package '%s'" % name,
            self._ctx.options.download)

        if dep_type == RUNTIME:
            self._ctx.env.append_value('RUNTIME_PIP_PACKAGES', [name])


class DebManager(PackageManager):
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
        p = subprocess.run(
            ['/usr/bin/dpkg-query', '--show', '--showformat', '${Package}\t${Version}\n'],
            stdout=subprocess.PIPE, check=True)

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
        cmd += ['--', '/usr/bin/apt-get', '-q', '-y', 'install', name]

        self._ctx.cmd_and_log(cmd, output=BOTH, env=env)

    def check_package(self, dep_type, name, version=None):
        super().check_package(
            dep_type, name, version, None,
            "Checking system package '%s'" % name,
            self._ctx.options.install_system_packages)


class UnsupportedDistManager(PackageManager):
    def compare_versions(self, v1, op, v2):
        raise RuntimeError

    def update_packages(self):
        raise RuntimeError

    def install_package(self, name, version=None, source=None):
        raise RuntimeError

    def check_package(self, dep_type, name, version=None, source=None):
        pass


class ThirdPartyBuilder(object):
    def __init__(self, ctx, name, archive_ext):
        self._ctx = ctx
        self.name = name
        self.archive_ext = archive_ext

    def download_url(self, version):
        raise NotImplementedError

    def archive_name(self, version):
        return '%s-%s%s' % (self.name, version, self.archive_ext)

    def download(self, download_url, target_path):
        total_bytes = 0
        with urllib.request.urlopen(download_url) as fp_in:
            with open(target_path + '.partial', 'wb') as fp_out:
                while True:
                    dat = fp_in.read(10240)
                    if not dat:
                        break
                    fp_out.write(dat)
                    total_bytes += len(dat)

        os.rename(target_path + '.partial', target_path)
        return total_bytes

    def unpack(self, archive_path, target_path):
        if archive_path.endswith('.zip'):
            base_dir = None
            with zipfile.ZipFile(archive_path) as fp:
                for path in fp.namelist():
                    while path:
                        path, b = os.path.split(path)
                        if not path:
                            if base_dir is None:
                                base_dir = b
                            elif b != base_dir:
                                raise RuntimeError(
                                    "No common base dir (%s)" % b)

                fp.extractall(os.path.dirname(archive_path))

            os.rename(os.path.join(os.path.dirname(archive_path), base_dir), target_path)

        elif archive_path.endswith('.tar.bz2'):
            base_dir = None
            with tarfile.open(archive_path, 'r:bz2') as fp:
                for path in fp.getnames():
                    while path:
                        path, b = os.path.split(path)
                        if not path:
                            if base_dir is None:
                                base_dir = b
                            elif b != base_dir:
                                raise RuntimeError(
                                    "No common base dir (%s)" % b)

                fp.extractall(os.path.dirname(archive_path))

            os.rename(os.path.join(os.path.dirname(archive_path), base_dir), target_path)

        elif archive_path.endswith('.tar.xz'):
            base_dir = None
            with tarfile.open(archive_path, 'r:xz') as fp:
                for path in fp.getnames():
                    while path:
                        path, b = os.path.split(path)
                        if not path:
                            if base_dir is None:
                                base_dir = b
                            elif b != base_dir:
                                raise RuntimeError(
                                    "No common base dir (%s)" % b)

                fp.extractall(os.path.dirname(archive_path))

            os.rename(os.path.join(os.path.dirname(archive_path), base_dir), target_path)

        else:
            self._ctx.fatal("Unsupported archive %s" % archive_path)

    def build(self, src_path):
        raise NotImplementedError

    def install(self, src_path):
        raise NotImplementedError

    def check(self, dep_type, version):
        if dep_type >= DEV and not self._ctx.env.ENABLE_TEST:
            return
        if dep_type >= VMTEST and not self._ctx.env.ENABLE_VMTEST:
            return

        self._ctx.start_msg("Checking '%s'" % self.name)
        install_sentinel_path = os.path.join(
            self._ctx.env.VIRTUAL_ENV, '.%s-%s-installed' % (self.name, version))
        if os.path.isfile(install_sentinel_path):
            self._ctx.end_msg(version)
            return
        self._ctx.end_msg('not found', 'YELLOW')

        build_path = os.path.join(
            self._ctx.env.VIRTUAL_ENV, 'build', '%s-%s' % (self.name, version))
        if not os.path.isdir(build_path):
            os.makedirs(build_path)

        archive_path = os.path.join(build_path, self.archive_name(version))
        if not os.path.isfile(archive_path):
            self._ctx.start_msg("Download '%s'" % self.archive_name(version))
            download_url = self.download_url(version)
            size = self.download(download_url, archive_path)
            self._ctx.end_msg('%d bytes' % size)

        src_path = os.path.join(build_path, 'src')
        if not os.path.isdir(src_path):
            self._ctx.start_msg("Unpack '%s'" % self.archive_name(version))
            self.unpack(archive_path, src_path)
            self._ctx.end_msg("ok")

        build_sentinel_path = os.path.join(build_path, '.built-complete')
        if not os.path.isfile(build_sentinel_path):
            self._ctx.start_msg("Build '%s'" % self.name)
            self.build(src_path)
            open(build_sentinel_path, 'w').close()
            self._ctx.end_msg("ok")

        self._ctx.start_msg("Install '%s'" % self.name)
        self.install(src_path)
        open(install_sentinel_path, 'w').close()
        self._ctx.end_msg(version)


class CSoundBuilder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'csound', '.zip')

    def download_url(self, version):
        return 'https://github.com/csound/csound/archive/%s.zip' % version

    def build(self, src_path):
        make_path = os.path.join(src_path, 'build')
        if not os.path.isdir(make_path):
            os.makedirs(make_path)

        self._ctx.cmd_and_log(
            ['cmake',
             '-DBUILD_PYTHON_INTERFACE=0',
             '-DBUILD_LINEAR_ALGEBRA_OPCODES=0',
             '-DCMAKE_INSTALL_PREFIX=' + self._ctx.env.VIRTUAL_ENV,
             os.path.abspath(src_path)
            ],
            cwd=make_path)
        self._ctx.cmd_and_log(
            ['make', '-j%d' % len(os.sched_getaffinity(0))],
            cwd=make_path)

    def install(self, src_path):
        make_path = os.path.join(src_path, 'build')
        self._ctx.cmd_and_log(
            ['make', 'install'],
            cwd=make_path)


class FaustBuilder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'faust', '.zip')

    def download_url(self, version):
        return 'https://github.com/grame-cncm/faust/archive/%s.zip' % version

    def build(self, src_path):
        self._ctx.cmd_and_log(
            ['make',
             '-j%d' % len(os.sched_getaffinity(0)),
             'PREFIX=' + self._ctx.env.VIRTUAL_ENV,
             'compiler'],
            cwd=src_path)

    def install(self, src_path):
        self._ctx.cmd_and_log(
            ['make',
             'PREFIX=' + self._ctx.env.VIRTUAL_ENV,
             'install'],
            cwd=src_path)


class FaustLibrariesBuilder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'faustlibraries', '.zip')

    def download_url(self, version):
        return 'https://github.com/grame-cncm/faustlibraries/archive/%s.zip' % version

    def build(self, src_path):
        pass

    def install(self, src_path):
        target_path = os.path.join(self._ctx.env.VIRTUAL_ENV, 'share', 'faustlibraries')
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        shutil.copytree(src_path, target_path)


class LilvBuilder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'lilv', '.zip')

    def download_url(self, version):
        # 'http://git.drobilla.net/cgit.cgi/lilv.git/snapshot/lilv-%s.tar.bz2' % version
        return 'https://github.com/odahoda/lilv/archive/master.zip'

    def build(self, src_path):
        os.chmod(os.path.join(src_path, 'waf'), 0o755)

        self._ctx.cmd_and_log(
            ['./waf',
             'configure',
             '--prefix=%s' % self._ctx.env.VIRTUAL_ENV,
             '--bindings',
             '--no-utils',
             '--no-bash-completion',
             '--test',
            ],
            cwd=src_path)
        self._ctx.cmd_and_log(
            ['./waf',
             'build',
            ],
            cwd=src_path)

    def install(self, src_path):
        self._ctx.cmd_and_log(
            ['./waf',
             'install',
            ],
            cwd=src_path)


class SuilBuilder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'suil', '.tar.bz2')

    def download_url(self, version):
        return 'http://git.drobilla.net/cgit.cgi/suil.git/snapshot/suil-%s.tar.bz2' % version

    def build(self, src_path):
        os.chmod(os.path.join(src_path, 'waf'), 0o755)

        self._ctx.cmd_and_log(
            ['./waf',
             'configure',
             '--prefix=%s' % self._ctx.env.VIRTUAL_ENV,
            ],
            cwd=src_path)
        self._ctx.cmd_and_log(
            ['./waf',
             'build',
            ],
            cwd=src_path)

    def install(self, src_path):
        self._ctx.cmd_and_log(
            ['./waf',
             'install',
            ],
            cwd=src_path)


class LV2Builder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'lv2', '.tar.xz')

    def download_url(self, version):
        return 'http://lv2plug.in/git/cgit.cgi/lv2.git/snapshot/lv2-%s.tar.xz' % version

    def build(self, src_path):
        os.chmod(os.path.join(src_path, 'waf'), 0o755)

        self._ctx.cmd_and_log(
            ['./waf',
             'configure',
             '--prefix=%s' % self._ctx.env.VIRTUAL_ENV,
            ],
            cwd=src_path)
        self._ctx.cmd_and_log(
            ['./waf',
             'build',
            ],
            cwd=src_path)

    def install(self, src_path):
        self._ctx.cmd_and_log(
            ['./waf',
             'install',
            ],
            cwd=src_path)


class ProtocBuilder(ThirdPartyBuilder):
    def __init__(self, ctx):
        super().__init__(ctx, 'protoc', '.zip')

    def download_url(self, version):
        return 'https://github.com/google/protobuf/archive/v%s.zip' % version

    def build(self, src_path):
        self._ctx.cmd_and_log(
            ['bash', 'autogen.sh'],
            cwd=src_path)
        self._ctx.cmd_and_log(
            ['./configure',
             '--prefix=%s' % self._ctx.env.VIRTUAL_ENV,
            ],
            cwd=src_path)
        self._ctx.cmd_and_log(
            ['make', '-j%d' % len(os.sched_getaffinity(0))],
            cwd=src_path)

    def install(self, src_path):
        self._ctx.cmd_and_log(
            ['make', 'install'],
            cwd=src_path)
