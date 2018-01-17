# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

from distutils import core
from distutils.command.build import build
from distutils.command.install import install
import urllib.request
import os
import os.path
import subprocess
import sys
import time
import tarfile

VERSION = '0.24.0'
FILENAME = 'lilv-%s.tar.bz2' % VERSION
DOWNLOAD_URL = 'http://git.drobilla.net/cgit.cgi/lilv.git/snapshot/%s' % FILENAME

assert os.getenv('VIRTUAL_ENV'), "Not running in a virtualenv."


class LilvMixin(object):
    user_options = [
        ('build-base=', 'b',
         "base directory for build library"),
        ]

    def initialize_options(self):
        self.build_base = os.path.join(os.getenv('VIRTUAL_ENV'), 'build', 'lilv')

    def finalize_options(self):
        pass

    @property
    def archive_path(self):
        return os.path.join(self.build_base, FILENAME)

    @property
    def src_dir(self):
        return os.path.join(self.build_base, 'src')


class BuildLilv(LilvMixin, core.Command):
    def run(self):
        if not os.path.isdir(self.build_base):
            os.makedirs(self.build_base)

        self._download_archive(self.archive_path)
        self._unpack_archive(self.archive_path, self.src_dir)
        self._configure(self.src_dir)
        self._build(self.src_dir)

    def _download_archive(self, archive_path):
        if os.path.exists(archive_path):
            return

        total_bytes = 0
        with urllib.request.urlopen(DOWNLOAD_URL) as fp_in:
            with open(archive_path + '.partial', 'wb') as fp_out:
                last_report = time.time()
                try:
                    while True:
                        dat = fp_in.read(10240)
                        if not dat:
                            break
                        fp_out.write(dat)
                        total_bytes += len(dat)
                        if time.time() - last_report > 1:
                            sys.stderr.write(
                                'Downloading %s: %d bytes\r'
                                % (DOWNLOAD_URL, total_bytes))
                            sys.stderr.flush()
                            last_report = time.time()
                finally:
                    sys.stderr.write('\033[K')
                    sys.stderr.flush()

        os.rename(archive_path + '.partial', archive_path)
        print('Downloaded %s: %d bytes' % (DOWNLOAD_URL, total_bytes))

    def _unpack_archive(self, archive_path, src_dir):
        if os.path.isdir(src_dir):
            return

        print("Extracting...")

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

            fp.extractall(self.build_base)

        os.rename(os.path.join(self.build_base, base_dir), src_dir)
        print("Extracted to %s" % src_dir)
        return src_dir

    def _configure(self, src_dir):
        if os.path.exists(os.path.join(src_dir, '.configure.complete')):
            return

        print("Running waf configure...")
        subprocess.run(
            ['./waf',
             'configure',
             '--prefix=%s' % os.getenv('VIRTUAL_ENV'),
             '--bindings',
             '--no-utils',
             '--no-bash-completion',
             '--test',
            ],
            cwd=src_dir,
            env=dict(
                os.environ,
                PKG_CONFIG_PATH=os.path.join(os.getenv('VIRTUAL_ENV'), 'lib', 'pkgconfig')),
            check=True)
        open(os.path.join(src_dir, '.configure.complete'), 'w').close()

    def _build(self, src_dir):
        if os.path.exists(os.path.join(src_dir, '.build.complete')):
            return

        print("Running waf build...")
        subprocess.run(
            ['./waf', 'build'],
            cwd=src_dir,
            check=True)
        open(os.path.join(src_dir, '.build.complete'), 'w').close()


class InstallLilv(LilvMixin, core.Command):
    @property
    def sentinel_path(self):
        return os.path.join(
            os.getenv('VIRTUAL_ENV'), '.lilv-%s-installed' % VERSION)

    def run(self):
        if os.path.exists(self.sentinel_path):
            return

        print("Running waf install...")
        subprocess.run(
            ['./waf', 'install'],
            cwd=self.src_dir,
            check=True)
        open(self.sentinel_path, 'w').close()

    def get_outputs(self):
        return [self.sentinel_path]


build.sub_commands.append(('build_lilv', None))
install.sub_commands.insert(0, ('install_lilv', None))


core.setup(
    name = 'lilv',
    version = VERSION,
    cmdclass = {
        'build_lilv': BuildLilv,
        'install_lilv': InstallLilv,
    },
    requires=['lv2'],
)
