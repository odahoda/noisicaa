#!/usr/bin/python3

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

# Important: This module must not import any other noisicaa modules.

import os
import os.path
import subprocess

# Exit codes of the main app.
EXIT_SUCCESS = 0
EXIT_EXCEPTION = 1
EXIT_RESTART = 17
EXIT_RESTART_CLEAN = 18

ROOT = os.path.abspath(os.path.dirname(__file__))

DATA_DIR = os.path.abspath(os.path.join(__file__, '..', '..', 'data'))

CACHE_DIR = os.path.abspath(os.path.join(os.path.expanduser('~'), '.cache', 'noisicaä'))

def __xdg_user_dir(resource):
    try:
        res = subprocess.run(['/usr/bin/xdg-user-dir', resource], stdout=subprocess.PIPE)
        return os.fsdecode(res.stdout.rstrip(b'\n'))
    except:
        return os.path.expanduser('~')

MUSIC_DIR = __xdg_user_dir('MUSIC')
for d in ['noisicaä', 'Noisicaä', 'noisicaa', 'Noisicaa']:
    if os.path.isdir(os.path.join(MUSIC_DIR, d)):
        PROJECT_DIR = os.path.join(MUSIC_DIR, d)
        break
else:
    PROJECT_DIR = MUSIC_DIR

# Test related stuff.
TESTLOG_DIR = os.path.abspath(os.path.join(__file__, '..', '..', 'testlogs'))
class TEST_OPTS(object):
    WRITE_PERF_STATS = False
    ENABLE_PROFILER = False
    PLAYBACK_BACKEND = 'null'

# Cleanup namespace
del os
del subprocess
