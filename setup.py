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
import os.path
import sys
from distutils import spawn
from distutils.core import setup
import distutils.command.build as _build
import distutils.command.install as _install


class build(_build.build):
    def run(self):
        if sys.version_info[0:2] < (3, 5):
            print("noisicaä required Python 3.5 or higher.")
            sys.exit(1)

        cmake_path = spawn.find_executable('cmake')
        if cmake_path is None:
            print("cmake is required to build noisicaä.")
            print("Please install cmake version >= 3.5 and re-run setup.")
            sys.exit(1)

        make_path = spawn.find_executable('make')
        if make_path is None:
            print("make is required to build noisicaä.")
            print("Please install make version >= 4.0 and re-run setup.")
            sys.exit(1)

        if not os.path.isdir(self.build_base):
            os.makedirs(self.build_base)

        old_cwd = os.getcwd()
        os.chdir(self.build_base)
        try:
            if not os.path.isfile('CMakeCache.txt'):
                spawn.spawn([cmake_path, '-G', 'Unix Makefiles', old_cwd])
            spawn.spawn([make_path, '-j%d' % len(os.sched_getaffinity(0))])
        finally:
            os.chdir(old_cwd)


class install(_install.install):
    def run(self):
        print("Installing not yet supported.")
        sys.exit(1)


setup(
    name = 'noisicaä',
    version = '0.1',
    author = 'Ben Niemann',
    author_email = 'pink@odahoda.de',
    url = 'https://github.com/odahoda/noisicaa',
    # license = 'TODO',
    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: End Users/Desktop',
        # TODO: 'License :: OSI Approved :: ',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Artistic Software',
        'Topic :: Multimedia :: Sound/Audio :: Editors',
    ],
    cmdclass = {
        'install': install,
        'build': build
    },
)
