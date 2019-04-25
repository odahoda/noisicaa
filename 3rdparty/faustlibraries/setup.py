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

from distutils import core
from distutils.command.build import build
from distutils.command.install import install
import urllib.request
import os
import os.path
import shutil
import subprocess
import sys
import time
import zipfile

VERSION = '0.20190330'
COMMIT_ID = '64a57f5693573ed73409f16c0d7ba420cde6111e'
DOWNLOAD_URL = 'https://github.com/grame-cncm/faustlibraries/archive/%s.zip' % COMMIT_ID

assert os.getenv('VIRTUAL_ENV'), "Not running in a virtualenv."


class FaustLibrariesMixin(object):
    user_options = [
        ('build-base=', 'b',
         "base directory for build library"),
        ]

    def initialize_options(self):
        self.build_base = os.path.join(os.getenv('VIRTUAL_ENV'), 'build', 'faustlibraries')

    def finalize_options(self):
        pass

    @property
    def zip_path(self):
        return os.path.join(self.build_base, 'faustlibraries-%s.zip' % VERSION)

    @property
    def src_dir(self):
        return os.path.join(self.build_base, 'src-%s' % VERSION)


class BuildFaustLibraries(FaustLibrariesMixin, core.Command):
    def run(self):
        if not os.path.isdir(self.build_base):
            os.makedirs(self.build_base)

        self._download_zip(self.zip_path)
        self._unpack_zip(self.zip_path, self.src_dir)

    def _download_zip(self, zip_path):
        if os.path.exists(zip_path):
            return

        total_bytes = 0
        with urllib.request.urlopen(DOWNLOAD_URL) as fp_in:
            with open(zip_path + '.partial', 'wb') as fp_out:
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

        os.rename(zip_path + '.partial', zip_path)
        print('Downloaded %s: %d bytes' % (DOWNLOAD_URL, total_bytes))

    def _unpack_zip(self, zip_path, src_dir):
        if os.path.isdir(src_dir):
            return

        print("Extracting...")

        base_dir = None
        with zipfile.ZipFile(zip_path) as fp:
            for path in fp.namelist():
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


class InstallFaustLibraries(FaustLibrariesMixin, core.Command):
    @property
    def sentinel_path(self):
        return os.path.join(
            os.getenv('VIRTUAL_ENV'), '.faustlibraries-%s-installed' % VERSION)

    @property
    def install_dir(self):
        return os.path.join(
            os.getenv('VIRTUAL_ENV'), 'share', 'faustlibraries')

    def run(self):
        if os.path.exists(self.sentinel_path):
            return

        print("Copy files...")
        shutil.rmtree(self.install_dir)
        shutil.copytree(self.src_dir, self.install_dir)
        open(self.sentinel_path, 'w').close()

    def get_outputs(self):
        return [self.sentinel_path]


build.sub_commands.append(('build_faustlibraries', None))
install.sub_commands.insert(0, ('install_faustlibraries', None))


core.setup(
    name = 'faustlibraries',
    version = VERSION,
    cmdclass = {
        'build_faustlibraries': BuildFaustLibraries,
        'install_faustlibraries': InstallFaustLibraries,
    },
)
