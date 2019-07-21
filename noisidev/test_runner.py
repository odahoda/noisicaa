#!/usr/bin/env python3

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

import argparse
import atexit
import contextlib
import itertools
import fnmatch
import logging
import os
import os.path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest

import coverage
import xmlrunner


SITE_PACKAGES_DIR = os.path.join(
    os.getenv('VIRTUAL_ENV'),
    'lib',
    'python%d.%d' % (sys.version_info[0], sys.version_info[1]),
    'site-packages')

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRCDIR = ROOTDIR
LIBDIR = os.path.join(ROOTDIR, 'build')
sys.path.insert(0, LIBDIR)

# Ensure that future imports from noisidev come from LIBDIR.
sys.modules.pop('noisidev')

os.environ['NOISICAA_DATA_DIR'] = os.path.join(LIBDIR, 'data')

# Set path to locally built 3rdparty libraries.
os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getenv('VIRTUAL_ENV'), 'lib')

# Tests should only see our test plugins.
os.environ['LV2_PATH'] = os.path.join(ROOTDIR, 'build', 'testdata', 'lv2')
os.environ['LADSPA_PATH'] = os.path.join(ROOTDIR, 'build', 'testdata', 'ladspa')


def bool_arg(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ('true', 'y', 'yes', 'on', '1'):
            return True
        if value.lower() in ('false', 'n', 'no', 'off', '0'):
            return False
        raise ValueError("Invalid value '%s'." % value)
    raise TypeError("Invalid type '%s'." % type(value).__name__)


class DisplayManager(object):
    def __init__(self, display):
        self.__display = display

        self.__xvfb_process = None

    def __xvfb_logger(self):
        logger = logging.getLogger('xvfb')
        for l in self.__xvfb_process.stdout:
            logger.info(l.rstrip().decode('ascii', 'replace'))
        self.__xvfb_process.wait()
        logger.info("Xvfb process terminated with returncode=%d", self.__xvfb_process.returncode)

    def __enter__(self):
        if self.__display == 'off':
            logging.info("Disabling X11 display")
            os.environ.pop('DISPLAY', None)
            return

        if self.__display == 'local':
            assert 'DISPLAY' in os.environ
            return

        assert self.__display == 'xvfb'

        disp_r, disp_w = os.pipe()
        try:
            self.__xvfb_process = subprocess.Popen(
                ['/usr/bin/Xvfb',
                 '-screen', '0', '1600x1200x24',
                 '-displayfd', '%d' % disp_w,
                ],
                pass_fds=[disp_w],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            atexit.register(self.__xvfb_process.kill)

            xvfb_logger_thread = threading.Thread(target=self.__xvfb_logger)
            xvfb_logger_thread.start()

            disp_num_str = b''
            while b'\n' not in disp_num_str and self.__xvfb_process.poll() is None:
                d = os.read(disp_r, 1)
                if not d:
                    break
                disp_num_str += d

            if self.__xvfb_process.poll() is not None:
                raise RuntimeError(
                    "Xvfb server terminated with rc=%d" % self.__xvfb_process.returncode)

            disp_num = int(disp_num_str.strip())

        finally:
            os.close(disp_r)
            os.close(disp_w)

        logging.info("Started Xvfb server on display :%d", disp_num)
        os.environ['DISPLAY'] = ':%d' % disp_num

    def __exit__(self, type, value, exc):
        if self.__xvfb_process is not None:
            self.__xvfb_process.terminate()
            self.__xvfb_process.wait()
            atexit.unregister(self.__xvfb_process.kill)


# class TestResult(unittest.TextTestResult):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         self.successes = set()

#     def addSuccess(self, case):
#         super().addSuccess(case)
#         self.successes.add(case.id())

#     def addSkip(self, case, reason):
#         super().addSkip(case, reason)
#         self.successes.add(case.id())


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('test_mod', type=str)
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='critical',
        help="Minimum level for log messages written to STDERR.")
    parser.add_argument('--store-results', default=None)
    parser.add_argument('--coverage', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--write-perf-stats', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--profile', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--rtcheck', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--gdb', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--pedantic', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--keep-temp', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--only-failed', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--fail-fast', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--playback-backend', type=str, default='null')
    parser.add_argument('--tags', default='unit,lint')
    parser.add_argument('--display', choices=['off', 'local', 'xvfb'], default='xvfb')
    args = parser.parse_args(argv[1:])

    if args.gdb:
        with open('/tmp/noisicaa.gdbinit', 'w') as fp:
            fp.write(textwrap.dedent('''\
                set print thread-events off
                set confirm off
                handle SIGPIPE nostop noprint pass

                python
                import gdb
                import sys
                import os
                sys.path.insert(0, "{site_packages}")
                def setup_python(event):
                    from Cython.Debugger import libpython
                gdb.events.new_objfile.connect(setup_python)
                end

                set $_exitcode = -1
                run
                if $_exitcode != -1
                  quit
                end
                bt
                '''.format(
                    site_packages=SITE_PACKAGES_DIR)))

        subargv = [
            '/usr/bin/gdb',
            '--quiet',
            '--command', '/tmp/noisicaa.gdbinit',
            '--args', sys.executable,
            '-m', 'noisidev.runtests']
        for arg, value in sorted(args.__dict__.items()):
            arg = arg.replace('_', '-')
            if arg == 'test_mod':
                continue
            elif arg == 'gdb':
                subargv.append('--%s=%s' % (arg, False))
            elif value != parser.get_default(arg):
                subargv.append('--%s=%s' % (arg, value))

        subargv.append('--')
        subargv.extend(args.test_mode)

        print(' '.join(subargv))
        os.execv(subargv[0], subargv)

    if args.rtcheck:
        subargv = [sys.executable, '-m', 'noisidev.runtests']
        for arg, value in sorted(args.__dict__.items()):
            arg = arg.replace('_', '-')
            if arg == 'test_mod':
                continue
            elif arg == 'rtcheck':
                subargv.append('--%s=%s' % (arg, False))
            elif value != parser.get_default(arg):
                subargv.append('--%s=%s' % (arg, value))

        subargv.append('--')
        subargv.extend(args.test_mod)

        env = dict(**os.environ)
        env['LD_PRELOAD'] = ':'.join([
            os.path.join(LIBDIR, 'noisicaa', 'audioproc', 'engine', 'librtcheck.so'),
            os.path.join(LIBDIR, 'noisicaa', 'audioproc', 'engine', 'librtcheck_preload.so')])
        print('LD_PRELOAD=' + env['LD_PRELOAD'])
        os.execve(subargv[0], subargv, env)

    if args.store_results:
        os.makedirs(args.store_results, exist_ok=True)

        # This is a workaround. Paths relative to test_data_path are very long - too long for
        # sockets. So use a shorter path, which just symlinks to the real one.
        test_data_path = '/tmp/noisicaa-tests-%016x' % random.getrandbits(63)
        os.symlink(args.store_results, test_data_path)
        atexit.register(os.unlink, test_data_path)

    else:
        test_data_path = tempfile.mkdtemp(prefix='noisicaa-tests-')
        if not args.keep_temp:
            atexit.register(shutil.rmtree, test_data_path)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    if args.store_results:
        logging.basicConfig(
            format='%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s',
            filename=os.path.join(test_data_path, 'debug.log'),
            filemode='w',
            level=logging.DEBUG)

    else:
        logging.basicConfig(
            format='%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s',
            level={
                'debug': logging.DEBUG,
                'info': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR,
                'critical': logging.CRITICAL,
            }[args.log_level])

    # Make loggers of 3rd party modules less noisy.
    for other in ['quamash']:
        logging.getLogger(other).setLevel(logging.WARNING)

    if args.coverage:
        cov = coverage.Coverage(
            source=['build/noisicaa', 'build/noisidev'],
            omit='*_*test.py',
            config_file=False)
        cov.set_option("run:branch", True)
        cov.start()

    from noisicaa import constants
    constants.TEST_OPTS.WRITE_PERF_STATS = args.write_perf_stats
    constants.TEST_OPTS.ENABLE_PROFILER = args.profile
    constants.TEST_OPTS.PLAYBACK_BACKEND = args.playback_backend
    constants.TEST_OPTS.ALLOW_UI = (args.display != 'off')
    constants.TEST_OPTS.TMP_DIR = test_data_path

    from noisicaa import core
    core.init_pylogging()

    from noisicaa.core import stacktrace
    stacktrace.init()

    logging.info("Loading module %s...", args.test_mod)
    __import__(args.test_mod)

    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromName(args.test_mod)

    assert list(suite), "No tests found in %s" % args.test_mod

    def flatten_suite(suite):
        for child in suite:
            if isinstance(child, unittest.TestSuite):
                yield from flatten_suite(child)
            else:
                yield child

    tags_to_run = set()
    for tag in args.tags.split(','):
        tag = tag.strip()
        assert tag in {'all', 'unit', 'lint', 'pylint', 'mypy', 'integration', 'perf'}
        tags_to_run.add(tag)

    # tests_to_run = None
    # if args.only_failed:
    #     tests_to_run = set()
    #     with open('/tmp/noisicaa-failed-tests.txt', 'r', encoding='utf-8') as fp:
    #         for test_id in fp:
    #             tests_to_run.add(test_id.strip())

    flat_suite = unittest.TestSuite()
    for case in flatten_suite(suite):
        runit = False
        if not hasattr(case, 'tags') or 'all' in tags_to_run or case.tags & tags_to_run:
            runit = True

        # if tests_to_run is not None and case.id() not in tests_to_run:
        #     runit = False

        if runit:
            flat_suite.addTest(case)

    # all_case_ids = set(case.id() for case in flat_suite)

    if args.store_results:
        runner = xmlrunner.XMLTestRunner(
            stream=open(os.path.join(test_data_path, 'test.log'), 'w'),
            output=open(os.path.join(test_data_path, 'results.xml'), 'wb'),
            verbosity=2,
            failfast=args.fail_fast)
    else:
        runner = unittest.TextTestRunner(
            # resultclass=TestResult,
            verbosity=2,
            failfast=args.fail_fast)

    with DisplayManager(args.display):
        try:
            unittest.installHandler()
            result = runner.run(flat_suite)
        finally:
            unittest.removeHandler()

    # with open('/tmp/noisicaa-failed-tests.txt', 'w', encoding='utf-8') as fp:
    #     for case_id in sorted(all_case_ids - result.successes):
    #         fp.write(case_id + '\n')

    if args.coverage:
        cov.stop()
        cov_data = cov.get_data()
        total_coverage = cov.html_report(
            directory='/tmp/noisicaä.coverage')

        file_coverages = []
        for path in sorted(cov_data.measured_files()):
            _, statements, _, missing, _ = cov.analysis2(path)
            try:
                file_coverage = 1.0 - 1.0 * len(missing) / len(statements)
            except ZeroDivisionError:
                file_coverage = 1.0
            file_coverages.append(
                (os.path.relpath(
                    path, os.path.abspath(os.path.dirname(__file__))),
                 file_coverage))
        file_coverages = sorted(file_coverages, key=lambda f: f[1])
        file_coverages = filter(lambda f: f[1] < 0.8, file_coverages)
        file_coverages = list(file_coverages)

        print()
        print("Total coverage: %.1f%%" % total_coverage)
        for path, file_coverage in file_coverages[:5]:
            print("% 3.1f%% %s" % (100 * file_coverage, path))
        print("Coverage report: file:///tmp/noisicaä.coverage/index.html")
        print()

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
