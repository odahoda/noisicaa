#!/usr/bin/python3

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

import cProfile
import os.path

import pyprof2calltree

from noisicaa.constants import TEST_OPTS

def profile(file_base, func):
    profiler = cProfile.Profile()
    ret = profiler.runcall(func)
    profile_path = os.path.join(TEST_OPTS.TMP_DIR, 'callgrind.out.' + file_base)
    pyprof2calltree.convert(profiler.getstats(), profile_path)
    return ret

def profile_method(func):
    def _wrapped(self):
        return profile(self.id(), lambda: func(self))

    return _wrapped
