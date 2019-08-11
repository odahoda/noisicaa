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

import email
import json
import os
import os.path
import pathlib
import shutil
import subprocess

import packaging.markers
import packaging.requirements
import packaging.utils

from waflib.Configure import conf
from waflib import Logs


@conf
def install_post_func(ctx):
    if ctx.cmd == 'install':
        ctx.add_post_fun(install_post)
    elif ctx.cmd == 'uninstall':
        ctx.add_post_fun(uninstall_post)

def install_post(ctx):
    ctx.install_runtime_pip_packages()


def uninstall_post(ctx):
    if os.path.isdir(ctx.env.LIBDIR):
        shutil.rmtree(ctx.env.LIBDIR)


@conf
def install_runtime_pip_packages(ctx):
    pip_path = os.path.join(ctx.env.VIRTUAL_ENV, 'bin', 'pip')
    site_packages_path = os.path.join(
        ctx.env.VIRTUAL_ENV, 'lib', 'python%s' % ctx.env.PYTHON_VERSION, 'site-packages')

    p = subprocess.run(
        [pip_path, '--disable-pip-version-check', 'list', '--format=json'],
        stdout=subprocess.PIPE, check=True)
    installed_packages = {
        packaging.utils.canonicalize_name(p['name']): (p['name'], p['version'])
        for p in json.loads(p.stdout.decode('utf-8'))}

    required_packages = set()

    package_env = {'extra': ''}

    queue = ctx.env.RUNTIME_PIP_PACKAGES[:]
    while queue:
        pkg = packaging.utils.canonicalize_name(queue.pop(0))
        if pkg in required_packages:
            continue

        required_packages.add(pkg)

        inst_name, version = installed_packages[pkg]
        dist_info_path = os.path.join(
            site_packages_path, '%s-%s.dist-info' % (inst_name.replace('-', '_'), version))
        with open(os.path.join(dist_info_path, 'METADATA'), 'rb') as fp:
            metadata = email.message_from_binary_file(fp)

        for req_str in metadata.get_all('Requires', []) + metadata.get_all('Requires-Dist', []):
            req = packaging.requirements.Requirement(req_str)
            if not req.marker or req.marker.evaluate(package_env):
                queue.append(req.name)

    for pkg in sorted(required_packages):
        inst_name, version = installed_packages[pkg]
        dist_info_path = os.path.join(
            site_packages_path, '%s-%s.dist-info' % (inst_name.replace('-', '_'), version))
        with open(os.path.join(dist_info_path, 'RECORD'), 'r') as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                path = line.split(',')[0]

                src_path = pathlib.Path(
                    os.path.abspath(os.path.join(site_packages_path, path)))
                try:
                    rel_path = src_path.relative_to(site_packages_path)
                except ValueError:
                    # File is not under site-packages.
                    continue

                dest_path = os.path.join(ctx.env.LIBDIR, str(rel_path))

                if not ctx.progress_bar:
                    Logs.info(
                        '%s+ install %s%s%s (from %s)',
                        Logs.colors.NORMAL, Logs.colors.BLUE, dest_path, Logs.colors.NORMAL,
                        src_path)

                if not os.path.isdir(os.path.dirname(dest_path)):
                    os.makedirs(os.path.dirname(dest_path))
                shutil.copyfile(str(src_path), dest_path)
                shutil.copystat(str(src_path), dest_path)
