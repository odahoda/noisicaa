#!/usr/bin/env python3

import argparse
import itertools
import fnmatch
import logging
import os
import os.path
import shutil
import subprocess
import sys
import textwrap
import unittest

import coverage

LIBDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'build'))
sys.path.insert(0, LIBDIR)

os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getenv('VIRTUAL_ENV'), 'lib')

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


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('selectors', type=str, nargs='*')
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='error',
        help="Minimum level for log messages written to STDERR.")
    parser.add_argument('--coverage', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--write-perf-stats', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--profile', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--gdb', nargs='?', type=bool_arg, const=True, default=True)
    parser.add_argument('--rebuild', nargs='?', type=bool_arg, const=True, default=True)
    parser.add_argument('--playback-backend', type=str, default='null')
    args = parser.parse_args(argv[1:])

    if args.gdb:
        with open('/tmp/noisicaa.gdbinit', 'w') as fp:
            fp.write(textwrap.dedent('''\
                set print thread-events off
                set $_exitcode = -1
                run
                if $_exitcode != -1
                  quit
                end
                bt
                '''))

        subargv = [
            '/usr/bin/gdb',
            '--quiet',
            '--command', '/tmp/noisicaa.gdbinit',
            '--args', sys.executable, __file__]
        for arg, value in sorted(args.__dict__.items()):
            arg = arg.replace('_', '-')
            if arg == 'selectors':
                continue
            elif arg == 'gdb':
                subargv.append('--%s=%s' % (arg, False))
            elif value != parser.get_default(arg):
                subargv.append('--%s=%s' % (arg, value))

        if args.selectors:
            subargv.append('--')
            subargv.extend(args.selectors)

        print(' '.join(subargv))
        os.execv(subargv[0], subargv)

    logging.basicConfig()
    logging.getLogger().setLevel({
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
        }[args.log_level])

    if args.rebuild:
        subprocess.run(['make', '-j4'], cwd=LIBDIR, check=True)

    from noisicaa import constants
    constants.TEST_OPTS.WRITE_PERF_STATS = args.write_perf_stats
    constants.TEST_OPTS.ENABLE_PROFILER = args.profile
    constants.TEST_OPTS.PLAYBACK_BACKEND = args.playback_backend

    from noisicaa import core
    core.init_pylogging()

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

    if args.coverage:
        cov = coverage.Coverage(
            source=['noisicaa'],
            omit='*_*test.py',
            config_file=False)
        cov.set_option("run:branch", True)
        cov.start()

    for dirpath, dirnames, filenames in os.walk(os.path.join(LIBDIR, 'noisicaa')):
        if '__pycache__' in dirnames:
            dirnames.remove('__pycache__')

        for filename in filenames:
            if not (fnmatch.fnmatch(filename, '*.py') or fnmatch.fnmatch(filename, '*.so')):
                continue

            filename = os.path.splitext(filename)[0]

            modpath = os.path.join(dirpath, filename)
            assert modpath.startswith(LIBDIR + '/')
            modpath = modpath[len(LIBDIR)+1:]
            modname = modpath.replace('/', '.')

            is_test = modname.endswith('test')
            is_unittest = modname.endswith('_test')

            if args.selectors:
                matched = False
                for selector in args.selectors:
                    if modname == selector:
                        matched = is_test
                    elif modname.startswith(selector):
                        matched = is_unittest
            else:
                matched = is_unittest

            if matched or args.coverage:
                logging.info("Loading module %s...", modname)
                __import__(modname)

            if not matched:
                continue

            modsuite = loader.loadTestsFromName(modname)
            suite.addTest(modsuite)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

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
