#!/usr/bin/env python3

import argparse
import fnmatch
import logging
import os
import os.path
import sys
import unittest

import coverage

import pyximport
pyximport.install(setup_args={'script_args': ['--verbose']})

LIBDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, LIBDIR)

from noisicaa import constants

os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getenv('VIRTUAL_ENV'), 'lib')

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('selectors', type=str, nargs='*')
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='error',
        help="Minimum level for log messages written to STDERR.")
    parser.add_argument('--nocoverage', action='store_true', default=False)
    parser.add_argument('--write_perf_stats', action='store_true', default=False)
    args = parser.parse_args(argv[1:])

    constants.TEST_OPTS.WRITE_PERF_STATS = args.write_perf_stats

    logging.basicConfig()
    logging.getLogger().setLevel({
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
        }[args.log_level if not args.debug else 'debug'])

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

    if not args.nocoverage:
        cov = coverage.Coverage(
            source=['noisicaa'],
            omit='*_*test.py',
            config_file=False)
        cov.set_option("run:branch", True)
        cov.start()

    for dirpath, dirnames, filenames in os.walk(
        os.path.join(LIBDIR, 'noisicaa')):
        if '__pycache__' in dirnames:
            dirnames.remove('__pycache__')

        for filename in filenames:
            if not (fnmatch.fnmatch(filename, '*.py') or fnmatch.fnmatch(filename, '*.pyx')):
                continue

            filename = os.path.splitext(filename)[0]

            modpath = os.path.join(dirpath, filename)
            assert modpath.startswith(LIBDIR + '/')
            modpath = modpath[len(LIBDIR)+1:]
            modname = modpath.replace('/', '.')

            if args.selectors:
                matched = False
                for selector in args.selectors:
                    if modname.startswith(selector):
                        matched = True
            else:
                matched = True

            is_test = modname.endswith('_test')

            if (is_test and matched) or not args.nocoverage:
                logging.info("Loading module %s...", modname)
                __import__(modname)

            if not is_test or not matched:
                continue

            modsuite = loader.loadTestsFromName(modname)
            suite.addTest(modsuite)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not args.nocoverage:
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
