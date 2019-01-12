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

import contextlib
import cProfile
import os.path
import tempfile

from noisicaa import constants

def profile(file_base, func):
    if not constants.TEST_OPTS.ENABLE_PROFILER:
        return func()

    profiler = cProfile.Profile()
    ret = profiler.runcall(func)
    profile_path = os.path.join(
        tempfile.gettempdir(), file_base + '.prof')
    profiler.dump_stats(profile_path)
    print('Profile written to %s' % profile_path)
    return ret

def profile_method(func):
    def _wrapped(self):
        return profile(self.id(), lambda: func(self))

    return _wrapped
