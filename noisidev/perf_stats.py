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

import csv
import datetime
import logging
import os.path
import pprint

import numpy
import cpuinfo

from noisicaa import constants

logger = logging.getLogger(__name__)


def write_frame_stats(filebase, testname, frame_times):
    frame_times = numpy.array(frame_times, dtype=numpy.int64)
    data = []
    data.append(
        ('datetime', datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))

    ci = cpuinfo.get_cpu_info()
    data.append(('CPU brand', ci['brand']))
    data.append(('CPU speed', ci['hz_advertised']))
    data.append(('CPU cores', ci['count']))

    data.append(('testname', testname))
    data.append(('#frames', len(frame_times)))
    data.append(('mean', frame_times.mean()))
    data.append(('stddev', frame_times.std()))

    for p in (50, 75, 90, 95, 99, 99.9):
        data.append(
            ('%.1fth %%tile' % p, numpy.percentile(frame_times, p)))

    logger.info("Frame stats:\n%s", pprint.pformat(data))

    if constants.TEST_OPTS.WRITE_PERF_STATS:
        with open(
                os.path.join(constants.TESTLOG_DIR, filebase + '.csv'),
                'a', newline='', encoding='utf-8') as fp:
            writer = csv.writer(fp, dialect=csv.unix_dialect)
            if fp.tell() == 0:
                writer.writerow([h for h, _ in data])
            writer.writerow([v for _, v in data])
