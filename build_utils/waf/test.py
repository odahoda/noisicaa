# -*- mode: python -*-

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

import datetime
import email
import fnmatch
import glob
import json
import os
import os.path
import pathlib
import shutil
import subprocess
import sys
import textwrap
import unittest

import coverage
import xunitparser

from waflib.Configure import conf
from waflib import Logs


ALL_TAGS = {'all', 'unit', 'lint', 'pylint', 'mypy', 'integration', 'perf'}

def options(ctx):
    grp = ctx.add_option_group('Test options')
    grp.add_option(
        '--tags',
        default='unit,lint',
        help="Comma separated list of test classes to run (%s) [default: unit,lint]" % ', '.join(sorted(ALL_TAGS)))
    grp.add_option(
        '--tests',
        action='append',
        default=None,
        help="Tests to run. Uses a prefix match and can contain globs. This flag can be used multiple times [default: all tests]")
    grp.add_option(
        '--fail-fast',
        action='store_true',
        default=False,
        help="Abort test run on first failure.")
    grp.add_option(
        '--only-failed',
        action='store_true',
        default=False,
        help="Only tests, which previously failed.")
    grp.add_option(
        '--coverage',
        action='store_true',
        default=False,
        help="Enable code coverage report.")


@conf
def init_test(ctx):
    if ctx.cmd == 'test':
        if not ctx.env.ENABLE_TEST:
            ctx.fatal("noisicaä has been configured without --enable-tests")

        ctx.TEST_STATE_PATH = os.path.join(ctx.out_dir, 'teststates')
        ctx.TEST_RESULTS_PATH = os.path.join(ctx.out_dir, 'testresults')
        ctx.TEST_TAGS = set(ctx.options.tags.split(','))
        for tag in ctx.TEST_TAGS:
            assert tag in ALL_TAGS

        ctx.add_pre_fun(test_init)
        ctx.add_post_fun(test_complete)


def test_init(ctx):
    if os.path.isdir(ctx.TEST_RESULTS_PATH):
        shutil.rmtree(ctx.TEST_RESULTS_PATH)

    if not ctx.options.only_failed and os.path.isdir(ctx.TEST_STATE_PATH):
        shutil.rmtree(ctx.TEST_STATE_PATH)


def test_complete(ctx):
    ctx.tests_failed = False

    ctx.collect_unittest_results()

    if {'all', 'lint', 'mypy'} & ctx.TEST_TAGS:
        ctx.collect_mypy_results()

    if {'all', 'lint', 'pylint'} & ctx.TEST_TAGS:
        ctx.collect_pylint_results()

    if ctx.options.coverage:
        ctx.collect_coverage_results()

    if ctx.tests_failed:
        ctx.fatal("Some tests failed")


@conf
def should_run_test(ctx, path):
    if not ctx.options.tests:
        return True

    mparts = path.relpath().split(os.sep)
    for selector in ctx.options.tests:
        sparts = selector.rstrip(os.sep).split(os.sep)
        if len(sparts) > len(mparts):
            continue
        matched = True
        for mpart, spart in zip(mparts[:len(sparts)], sparts):
            if not fnmatch.fnmatch(mpart, spart):
                matched = False
        if matched:
            return True


@conf
def record_test_state(ctx, test_name, state):
    state_path = os.path.join(ctx.TEST_STATE_PATH, test_name)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, 'w') as fp:
        fp.write('1' if state else '0')


@conf
def get_test_state(ctx, test_name):
    state_path = os.path.join(ctx.TEST_STATE_PATH, test_name)
    if os.path.isfile(state_path):
        with open(state_path, 'r') as fp:
            return bool(int(fp.read()))

    return False


class TestCase(xunitparser.TestCase):
    # This override only exists, because the original has a docstring, which shows up in the
    # output...
    def runTest(self):
        super().runTest()


class TextTestResult(unittest.TextTestResult, xunitparser.TestResult):
    def addSuccess(self, test):
        if self.showAll and test.time is not None:
            self.stream.write('[%dms] ' % (test.time / datetime.timedelta(milliseconds=1)))
        super().addSuccess(test)


class Parser(xunitparser.Parser):
    TC_CLASS = TestCase


@conf
def collect_unittest_results(ctx):
    def flatten_suite(suite):
        for child in suite:
            if isinstance(child, unittest.TestSuite):
                yield from flatten_suite(child)
            else:
                yield child

    all_tests = unittest.TestSuite()
    total_time = datetime.timedelta()
    for result_path in glob.glob(os.path.join(ctx.TEST_RESULTS_PATH, '*', 'results.xml')):
        if os.path.getsize(result_path) == 0:
            continue

        try:
            ts, tr = Parser().parse(result_path)
        except Exception as exc:
            print("Failed to parse %s" % result_path)
            raise
        for tc in flatten_suite(ts):
            all_tests.addTest(tc)
            if tc.time is not None:
                total_time += tc.time

    if not list(all_tests):
        return

    sorted_tests = unittest.TestSuite()
    for tc in sorted(all_tests, key=lambda tc: (tc.classname, tc.methodname)):
        sorted_tests.addTest(tc)

    stream = unittest.runner._WritelnDecorator(sys.stderr)

    result = TextTestResult(stream, True, verbosity=2)
    result.startTestRun()
    try:
        sorted_tests(result)
    finally:
        result.stopTestRun()

    result.printErrors()
    stream.writeln(result.separator2)
    run = result.testsRun
    stream.writeln("Ran %d test%s in %s" %
                   (run, run != 1 and "s" or "", total_time))
    stream.writeln()

    infos = []
    if not result.wasSuccessful():
        msg = "FAILED"
        if result.failures:
            infos.append("failures=%d" % len(result.failures))
        if result.errors:
            infos.append("errors=%d" % len(result.errors))
    else:
        msg = "OK"
    if result.skipped:
        infos.append("skipped=%d" % len(result.skipped))
    if result.expectedFailures:
        infos.append("expected failures=%d" % len(result.expectedFailures))
    if result.unexpectedSuccesses:
        infos.append("unexpected successes=%d" % len(result.unexpectedSuccesses))

    if infos:
        msg += " (%s)" % ", ".join(infos)

    if not result.wasSuccessful():
        Logs.info(Logs.colors.RED + msg)
        ctx.tests_failed = True
    else:
        Logs.info(msg)


@conf
def collect_mypy_results(ctx):
    Logs.info(Logs.colors.BLUE + "Collecting mypy data...")

    issues_found = False

    for result_path in glob.glob(os.path.join(ctx.TEST_RESULTS_PATH, '*', 'mypy.log')):
        with open(result_path, 'r') as fp:
            log = fp.read()
            if log:
                issues_found = True
                sys.stderr.write(log)
                sys.stderr.write('\n\n')

    if issues_found:
        ctx.tests_failed = True
        Logs.info(Logs.colors.RED + "mypy found some issues")
    else:
        Logs.info(Logs.colors.GREEN + "No issues found")
        Logs.info('')


@conf
def collect_pylint_results(ctx):
    Logs.info(Logs.colors.BLUE + "Collecting pylint data...")

    issues_found = False

    for result_path in glob.glob(os.path.join(ctx.TEST_RESULTS_PATH, '*', 'pylint.log')):
        with open(result_path, 'r') as fp:
            log = fp.read()
            if log:
                issues_found = True
                sys.stderr.write(log)
                sys.stderr.write('\n\n')

    if issues_found:
        ctx.tests_failed = True
        Logs.info(Logs.colors.RED + "pylint found some issues")
    else:
        Logs.info(Logs.colors.GREEN + "No issues found")
        Logs.info('')


@conf
def collect_coverage_results(ctx):
    Logs.info(Logs.colors.BLUE + "Collecting coverage data...")

    cov = coverage.Coverage()
    data = cov.get_data()
    for result_path in glob.glob(os.path.join(ctx.TEST_RESULTS_PATH, '*', 'coverage.data')):
        d = coverage.CoverageData()
        d.read_file(result_path)
        data.update(d)

    report_path = os.path.join(ctx.TEST_RESULTS_PATH, 'coverage')
    total_coverage = cov.html_report(directory=report_path)
    Logs.info(Logs.colors.GREEN + "Total coverage: %.1f%%" % total_coverage)
    Logs.info(Logs.colors.GREEN + "Coverage report: file://%s/index.html" % report_path)
    Logs.info('')
