#!/usr/bin/python3

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
