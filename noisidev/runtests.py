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
import atexit
import contextlib
import itertools
import fnmatch
import logging
import os
import os.path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest

import coverage
from mypy import api as mypy
import pylint.lint
import pylint.reporters

# --- HACK ---
# pylint adds the cwd to sys.path <quote>to have a correct behaviour</quote>.
# In this case, this is not the correct behavior, because it causes the module to be loaded
# from the src directory and not the build directory. And this causes it to not find cython
# or generated *_py2 modules.
# We solve this with monkey patching...
@contextlib.contextmanager
def fix_import_path(args):
    yield
pylint.lint.fix_import_path = fix_import_path

SITE_PACKAGES_DIR = os.path.join(
    os.getenv('VIRTUAL_ENV'),
    'lib',
    'python%d.%d' % (sys.version_info[0], sys.version_info[1]),
    'site-packages')

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRCDIR = ROOTDIR
LIBDIR = os.path.join(ROOTDIR, 'build')
sys.path.insert(0, LIBDIR)

# Ensure that future imports from noisidev come from LIBDIR.
sys.modules.pop('noisidev')

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


class MypyMessageCollector(object):
    def __init__(self):
        self.messages = []

    def append(self, msg):
        self.messages.append(msg)

    def extend(self, msgs):
        self.messages.extend(msgs)

    def print_report(self):
        if not self.messages:
            return

        sys.stderr.write(
            "\n==== mypy report =====================================================\n\n")
        fmt = '{path}:{line}: [{type}] {msg}\n'
        for msg in self.messages:
            sys.stderr.write(fmt.format(**msg))
        sys.stderr.write("\n\n")


class PylintMessageCollector(object):
    def __init__(self):
        self.messages = []

    def append(self, msg):
        self.messages.append(msg)

    def extend(self, msgs):
        self.messages.extend(msgs)

    def print_report(self):
        if not self.messages:
            return

        sys.stderr.write(
            "\n==== pylint report ===================================================\n\n")
        fmt = '{path}:{line}: [{msg_id}({symbol})] {msg}\n'
        for msg in self.messages:
            # The path that pylint reported is relative to the build dir. But we want to
            # show the path to the source dir, so emacs can jump to the right file.
            path = msg.path
            if path.startswith('build/'):
                path = path[6:]
            msg = msg._replace(path=path)
            sys.stderr.write(fmt.format(**msg._asdict()))
        sys.stderr.write("\n\n")


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
    def __init__(self, *, modname, method_name, pedantic, pylint_collector, mypy_collector):
        super().__init__(method_name)

        self.__modname = modname
        self.__method_name = method_name
        self.__pedantic = pedantic
        self.__pylint_collector = pylint_collector
        self.__mypy_collector = mypy_collector

    def __str__(self):
        return '%s (%s)' % (self.__method_name, self.__modname)

    # TODO: Add more stuff to the whitelist. Eventually all messages should be enabled
    #   (i.e. always running in pedantic mode), but right now there are too many
    #   false-positives.
    pylint_whitelist = {
        'attribute-defined-outside-init',
        'bad-classmethod-argument',
        'logging-not-lazy',
        'trailing-newlines',
        'trailing-whitespace',
        'unused-import',
        'useless-super-delegation',
    }

    def test_pylint(self):
        src_path = os.path.join(SRCDIR, os.path.join(*self.__modname.split('.')) + '.py')
        src = open(src_path, 'r').read()

        is_unclean = False
        unclean_lineno = -1
        for lineno, line in enumerate(src.splitlines(), 1):
            if re.match(r'^#\s*pylint:\s*skip-file\s*$', line):
                self.skipTest('pylint disabled for this file')
            if re.match(r'^#\s*TODO:\s*pylint-unclean\s*$', line):
                is_unclean = True
                unclean_lineno = lineno

        be_pedantic = self.__pedantic or not is_unclean

        args = [
            '--rcfile=%s' % os.path.join(ROOTDIR, 'bin', 'pylintrc'),
            self.__modname,
        ]

        reporter = PylintReporter()
        PylintRunner(args, reporter=reporter, exit=False)

        messages = list(reporter.messages)

        if is_unclean and len(messages) < 3:
            self.__pylint_collector.extend(messages)
            msg = "\nFile \"%s\", line %d, is marked as pylint-unclean" % (src_path, unclean_lineno)
            if not messages:
                msg += ", but no issues were reported."
            elif len(messages) == 1:
                msg += ", but only one issue was reported."
            else:
                msg += ", but only %d issues were reported." % len(messages)
            self.fail(msg)

        if not be_pedantic:
            messages = [msg for msg in messages if msg.symbol in self.pylint_whitelist]

        if messages:
            self.__pylint_collector.extend(messages)
            self.fail("pylint reported issues.")

    def test_mypy(self):
        if self.__modname.split('.')[-1] == '__init__':
            self.skipTest('mypy disabled for this file')

        src_path = os.path.join(SRCDIR, os.path.join(*self.__modname.split('.')) + '.py')
        src = open(src_path, 'r').read()

        is_unclean = False
        unclean_lineno = -1
        for lineno, line in enumerate(src.splitlines(), 1):
            if re.match(r'^#\s*mypy:\s*skip-file\s*$', line):
                self.skipTest('mypy disabled for this file')
            if re.match(r'^#\s*TODO:\s*mypy-unclean\s*$', line):
                is_unclean = True
                unclean_lineno = lineno

        be_pedantic = self.__pedantic or not is_unclean

        mypy_ini_path = os.path.join(os.path.dirname(__file__), 'mypy.ini')
        try:
            os.environ['MYPYPATH'] = SITE_PACKAGES_DIR
            old_cwd = os.getcwd()
            os.chdir(LIBDIR)

            stdout, stderr, rc = mypy.run(
                ['--config-file', mypy_ini_path,
                 '--cache-dir=%s' % os.path.join(LIBDIR, 'mypy-cache'),
                 '--show-traceback',
                 '-m', self.__modname
                ])
        finally:
            os.chdir(old_cwd)
            os.environ.pop('MYPYPATH')

        if stderr:
            sys.stderr.write(stderr)

        messages = []
        for line in stdout.splitlines(False):
            m = re.match(r'([^:]+):(\d+): ([a-z]+): (.*)$', line)
            if m is None:
                self.fail("Unrecognized mypy output: %s" % line)
            msg = dict(
                path=m.group(1),
                line=m.group(2),
                type=m.group(3),
                msg=m.group(4),
            )
            if msg['type'] == 'note':
                continue
            messages.append(msg)

        # if is_unclean and len(messages) < 3:
        #     self.__mypy_collector.extend(messages)
        #     msg = "\nFile \"%s\", line %d, is marked as mypy-unclean" % (src_path, unclean_lineno)
        #     if not messages:
        #         msg += ", but no issues were reported."
        #     elif len(messages) == 1:
        #         msg += ", but only one issue was reported."
        #     else:
        #         msg += ", but only %d issues were reported." % len(messages)
        #     self.fail(msg)

        if be_pedantic and messages:
            self.__mypy_collector.extend(messages)
            self.fail("mypy reported issues.")


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


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('selectors', type=str, nargs='*')
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='critical',
        help="Minimum level for log messages written to STDERR.")
    parser.add_argument('--coverage', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--write-perf-stats', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--profile', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--gdb', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--rebuild', nargs='?', type=bool_arg, const=True, default=True)
    parser.add_argument('--pedantic', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--builtin-tests', nargs='?', type=bool_arg, const=True, default=True)
    parser.add_argument('--keep-temp', nargs='?', type=bool_arg, const=True, default=False)
    parser.add_argument('--playback-backend', type=str, default='null')
    parser.add_argument('--mypy', type=bool_arg, default=True)
    parser.add_argument('--display', choices=['off', 'local', 'xvfb'], default='xvfb')
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
                    site_packages=SITE_PACKAGES_DIR)))

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

    # Make loggers of 3rd party modules less noisy.
    for other in ['quamash']:
        logging.getLogger(other).setLevel(logging.WARNING)

    if args.rebuild:
        subprocess.run([sys.executable, 'setup.py', 'build'], cwd=ROOTDIR, check=True)

    tmp_dir = tempfile.mkdtemp(prefix='noisicaa-tests-')
    if not args.keep_temp:
        atexit.register(shutil.rmtree, tmp_dir)

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
    constants.TEST_OPTS.TMP_DIR = tmp_dir

    from noisicaa import core
    core.init_pylogging()

    from noisicaa.core import stacktrace
    stacktrace.init()

    pylint_collector = PylintMessageCollector()
    mypy_collector = MypyMessageCollector()

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

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

            if (args.builtin_tests
                    and fnmatch.fnmatch(filename, '*.py')
                    and not fnmatch.fnmatch(filename, '*_pb2.py')):
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
                        if method_name == 'test_mypy' and not args.mypy:
                            continue

                        suite.addTest(test_cls(
                            modname=modname,
                            method_name=method_name,
                            pedantic=args.pedantic,
                            pylint_collector=pylint_collector,
                            mypy_collector=mypy_collector,
                        ))

    runner = unittest.TextTestRunner(verbosity=2)
    with DisplayManager(args.display):
        result = runner.run(suite)

    pylint_collector.print_report()
    mypy_collector.print_report()

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
