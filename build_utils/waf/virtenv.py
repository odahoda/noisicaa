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


DEFAULT_VENVDIR = os.path.expanduser('~/.local/share/virtualenvs/noisicaa')


def options(ctx):
    grp = ctx.add_option_group('Virtual Environment options')
    grp.add_option('--venvdir', action='store', default=None, help='Where to setup the virtual environment [default: %s]' % DEFAULT_VENVDIR)
    grp.add_option('--download', action='store_true', default=False, help='Download and install missing packages into virtual environment')
    grp.add_option('--install-system-packages', action='store_true', default=False, help='Download and install missing system package (requires `sudo` priviledge)')


def configure(ctx):
    ctx.check_virtual_env()

    pip_mgr = PipManager(ctx)

    ctx.start_msg("Query PIP for installed packages")
    pip_mgr.update_packages()
    ctx.to_log('Installed PIP packages:')
    for name, version in pip_mgr.packages:
        ctx.to_log('  %s: %s' % (name, version))
    ctx.end_msg("ok")

    # Basic venv stuff:
    ctx.check_pip_package(pip_mgr, 'pip', version='>=19.0')
    ctx.check_pip_package(pip_mgr, 'setuptools', version='>=41.0')
    ctx.check_pip_package(pip_mgr, 'wheel', version='>=0.33')

    # Runtime dependencies:
    # TODO: install those directly, not via PIP
    # TODO: 'ubuntu', '<17.10'),
    #ctx.check_pip_package(pip_mgr, 'csound', source='./3rdparty/csound/'),
    # TODO: 'ubuntu', '<17.10'),
    #ctx.check_pip_package(pip_mgr, 'lv2', source='./3rdparty/lv2/'),
    ctx.check_pip_package(pip_mgr, 'lilv', source='./3rdparty/lilv/'),
    ctx.check_pip_package(pip_mgr, 'suil', source='./3rdparty/suil/'),
    ctx.check_pip_package(pip_mgr, 'PyGObject'),
    ctx.check_pip_package(pip_mgr, 'PyQt5'),
    ctx.check_pip_package(pip_mgr, 'eventfd'),
    ctx.check_pip_package(pip_mgr, 'gbulb'),
    ctx.check_pip_package(pip_mgr, 'lucky-humanize'),
    ctx.check_pip_package(pip_mgr, 'numpy'),
    ctx.check_pip_package(pip_mgr, 'portalocker'),
    ctx.check_pip_package(pip_mgr, 'posix-ipc'),
    ctx.check_pip_package(pip_mgr, 'protobuf', version='3.7.1'),
    ctx.check_pip_package(pip_mgr, 'psutil'),
    ctx.check_pip_package(pip_mgr, 'PyAudio'),
    ctx.check_pip_package(pip_mgr, 'pyparsing'),
    # TODO: get my changes upstream and use regular quamash package from pip.
    ctx.check_pip_package(pip_mgr, 'Quamash', source='git+https://github.com/odahoda/quamash.git#egg=quamash'),
    ctx.check_pip_package(pip_mgr, 'sortedcontainers'),
    ctx.check_pip_package(pip_mgr, 'toposort'),
    ctx.check_pip_package(pip_mgr, 'urwid'),

    # Build dependencies
    # TODO: install those directly, not via PIP
    ctx.check_pip_package(pip_mgr, 'protoc', source='./3rdparty/protoc/'),
    ctx.check_pip_package(pip_mgr, 'faust', source='./3rdparty/faust/'),
    ctx.check_pip_package(pip_mgr, 'faustlibraries', source='./3rdparty/faustlibraries/'),
    ctx.check_pip_package(pip_mgr, 'cssutils'),
    ctx.check_pip_package(pip_mgr, 'Cython', version='0.29.6'),
    ctx.check_pip_package(pip_mgr, 'Jinja2'),
    ctx.check_pip_package(pip_mgr, 'pkgconfig'),
    ctx.check_pip_package(pip_mgr, 'PyYAML'),
    # TODO: get my changes upstream and use regular mypy-protobuf package from pip.
    ctx.check_pip_package(pip_mgr, 'mypy-protobuf', source='git+https://github.com/odahoda/mypy-protobuf.git#egg=mypy-protobuf&subdirectory=python'),

    # Dev dependencies
    ctx.check_pip_package(pip_mgr, 'asynctest'),
    ctx.check_pip_package(pip_mgr, 'async-generator'),
    ctx.check_pip_package(pip_mgr, 'coverage'),
    ctx.check_pip_package(pip_mgr, 'mox3'),
    ctx.check_pip_package(pip_mgr, 'py-cpuinfo'),
    ctx.check_pip_package(pip_mgr, 'pyfakefs'),
    ctx.check_pip_package(pip_mgr, 'pylint', version='2.3.1'),
    ctx.check_pip_package(pip_mgr, 'mypy', version='0.701'),
    ctx.check_pip_package(pip_mgr, 'mypy-extensions'),
    ctx.check_pip_package(pip_mgr, 'PyGObject-stubs'),

    # For indicator-cpufreq
    ctx.check_pip_package(pip_mgr, 'dbus-python'),
    ctx.check_pip_package(pip_mgr, 'python-distutils-extra', source='bzr+lp:python-distutils-extra#egg=python-distutils-extra'),
    ctx.check_pip_package(pip_mgr, 'indicator-cpufreq', source='bzr+lp:indicator-cpufreq#egg=indicator-cpufreq'),

    # VMtest dependencies:
    ctx.check_pip_package(pip_mgr, 'paramiko'),
    ctx.check_pip_package(pip_mgr, 'python-xlib'),

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


class PipManager(object):
    def __init__(self, ctx):
        self.__ctx = ctx

        self.__pip_path = os.path.join(self.__ctx.env.VIRTUAL_ENV, 'bin', 'pip')
        self.__pip_cmd = [self.__pip_path, '--disable-pip-version-check']
        self.__packages = {}

    @property
    def packages(self):
        return sorted(self.__packages.items())

    def is_installed(self, pkg):
        return pkg in self.__packages

    def version(self, pkg):
        return self.__packages[pkg]

    def split_spec(self, spec):
        if spec.startswith('<=') or spec.startswith('>=') or spec.startswith('=='):
            return spec[:2], spec[2:]

        if spec.startswith('<') or spec.startswith('>'):
            return spec[:1], spec[1:]

        return '==', spec

    def check_version(self, pkg, expected_spec):
        have = distutils.version.LooseVersion(self.version(pkg))

        op_name, version = self.split_spec(expected_spec)
        op = {
            '<=': operator.le,
            '>=': operator.ge,
            '<': operator.lt,
            '>': operator.gt,
            '==': operator.eq,
        }[op_name]
        expected = distutils.version.LooseVersion(version)

        return op(have, expected)

    def update_packages(self):
        p = subprocess.run(self.__pip_cmd + ['list', '--format=json'], stdout=subprocess.PIPE, check=True)
        self.__packages = {p['name']: p['version'] for p in json.loads(p.stdout)}

    def install_package(self, name, version=None, source=None):
        if source:
            spec = source
        else:
            spec = name
            if version:
                op, version = self.split_spec(version)
                spec += op
                spec += version
        self.__ctx.cmd_and_log(self.__pip_cmd + ['install', '-U', spec], output=BOTH)


@conf
def check_pip_package(ctx, mgr, name, version=None, source=None):
    ctx.start_msg("Checking PIP package '%s'" % name)
    need_install = False
    if not mgr.is_installed(name):
        ctx.to_log("Package is not installed")
        need_install = True

    else:
        ctx.to_log("Found installed version %s" % mgr.version(name))
        if version and not mgr.check_version(name, version):
            ctx.to_log("Requirement '%s' not met, requires update" % version)
            need_install = True

    if need_install:
        if not ctx.options.download:
            ctx.to_log("Running in offline mode, can't install package myself")
            ctx.fatal("missing")

        try:
            mgr.install_package(name, version, source)
        except WafError as exc:
            ctx.fatal("Failed to install pip package '%s'" % name)

        mgr.update_packages()

    ctx.end_msg(mgr.version(name))
