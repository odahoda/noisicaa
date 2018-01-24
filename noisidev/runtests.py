#!/usr/bin/env python3

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

import argparse
import itertools
import fnmatch
import logging
import os
import os.path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

import coverage
import pylint.lint
import pylint.reporters

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LIBDIR = os.path.join(ROOTDIR, 'build')
sys.path.insert(0, LIBDIR)

# Ensure that future imports from noisidev come from LIBDIR.
sys.modules.pop('noisidev')

os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getenv('VIRTUAL_ENV'), 'lib')

# Ensure all tests work without X.
os.environ.pop('DISPLAY', None)


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


class PylintReporter(pylint.reporters.CollectingReporter):
    def _display(self, layout):
        pass


class PylintLinter(pylint.lint.PyLinter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quiet = 1


class PylintRunner(pylint.lint.Run):
    LinterClass = PylintLinter


class BuiltinPyTests(unittest.TestCase):
    def __init__(self, *, modname, method_name, pedantic):
        super().__init__(method_name)

        self.__modname = modname
        self.__method_name = method_name
        self.__pedantic = pedantic

    def __str__(self):
        return '%s (%s)' % (self.__method_name, self.__modname)

    # TODO: Add more stuff to the whitelist. Eventually all messages should be enabled
    #   (i.e. always running in pedantic mode), but right now there are too many
    #   false-positives.
    pylint_whitelist = [
        'trailing-whitespace',
        'unused-import',
        'attribute-defined-outside-init',
        'bad-classmethod-argument',
        'logging-not-lazy',
        'useless-super-delegation',
    ]

    def test_pylint(self):
        args = ['--rcfile=%s' % os.path.join(ROOTDIR, 'bin', 'pylintrc')]

        if not self.__pedantic:
            args += [
                '--disable=all',
                '--enable=%s' % ','.join(self.pylint_whitelist),
            ]

        args += [self.__modname]

        reporter = PylintReporter()
        PylintRunner(args, reporter=reporter, exit=False)
        if reporter.messages:
            sys.stderr.write('\n')
            for msg in reporter.messages:
                sys.stderr.write(msg.format('{path}:{line}: [{msg_id}({symbol})] {msg}\n'))
            self.fail("pylint reported issues.")


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
    parser.add_argument('--pedantic', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--builtin-tests', nargs='?', type=bool_arg, const=True, default=True)
    parser.add_argument('--keep-temp', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--playback-backend', type=str, default='null')
    args = parser.parse_args(argv[1:])

    if args.gdb:
        with open('/tmp/noisicaa.gdbinit', 'w') as fp:
            fp.write(textwrap.dedent('''\
                set print thread-events off
                set confirm off

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
                    site_packages=os.path.join(
                        os.getenv('VIRTUAL_ENV'),
                        'lib',
                        'python%d.%d' % (sys.version_info[0], sys.version_info[1]),
                        'site-packages'))))

        subargv = [
            '/usr/bin/gdb',
            '--quiet',
            '--command', '/tmp/noisicaa.gdbinit',
            '--args', sys.executable,
            '-m', 'noisidev.runtests']
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

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    logging.basicConfig(
        format='%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s',
        level={
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL,
        }[args.log_level])

    if args.rebuild:
        subprocess.run([sys.executable, 'setup.py', 'build'], cwd=ROOTDIR, check=True)

    from noisicaa import constants
    constants.TEST_OPTS.WRITE_PERF_STATS = args.write_perf_stats
    constants.TEST_OPTS.ENABLE_PROFILER = args.profile
    constants.TEST_OPTS.PLAYBACK_BACKEND = args.playback_backend
    constants.TEST_OPTS.TMP_DIR = tempfile.mkdtemp(prefix='noisicaa-tests-')

    from noisicaa import core
    core.init_pylogging()

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

    if args.coverage:
        cov = coverage.Coverage(
            source=['build/noisicaa'],
            omit='*_*test.py',
            config_file=False)
        cov.set_option("run:branch", True)
        cov.start()

    for dirpath, dirnames, filenames in os.walk(os.path.join(LIBDIR, 'noisicaa')):
        for ignore_dir in ('__pycache__', 'testdata'):
            if ignore_dir in dirnames:
                dirnames.remove(ignore_dir)

        dirnames.sort()

        for filename in sorted(filenames):
            if (not (fnmatch.fnmatch(filename, '*.py') or fnmatch.fnmatch(filename, '*.so'))
                or fnmatch.fnmatch(filename, 'lib*.so')):
                continue

            basename = os.path.splitext(filename)[0]
            modpath = os.path.join(dirpath, basename)
            assert modpath.startswith(LIBDIR + '/')
            modpath = modpath[len(LIBDIR)+1:]
            modname = modpath.replace('/', '.')

            if args.coverage:
                logging.info("Loading module %s...", modname)
                __import__(modname)

            is_test = modname.endswith('test')
            is_unittest = modname.endswith('_test')
            if is_test:
                if args.selectors:
                    matched = False
                    for selector in args.selectors:
                        if modname == selector:
                            matched = is_test
                        elif modname.startswith(selector):
                            matched = is_unittest
                else:
                    matched = is_unittest

                if matched:
                    modsuite = loader.loadTestsFromName(modname)
                    suite.addTest(modsuite)

            if args.builtin_tests and fnmatch.fnmatch(filename, '*.py'):
                if args.selectors:
                    matched = False
                    for selector in args.selectors:
                        if modname.startswith(selector):
                            matched = True
                else:
                    matched = True

                if matched:
                    test_cls = BuiltinPyTests
                    for method_name in loader.getTestCaseNames(test_cls):
                        suite.addTest(test_cls(
                            modname=modname,
                            method_name=method_name,
                            pedantic=args.pedantic,
                        ))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not args.keep_temp:
        shutil.rmtree(constants.TEST_OPTS.TMP_DIR)

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
