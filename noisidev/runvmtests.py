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

import asyncio
import argparse
import logging
import os
import os.path
import sys

from . import testvm
from . import vmtests

# VMs = {}

# def register_vm(vm):
#     assert vm.name not in VMs
#     VMs[vm.name] = vm

# register_vm(ubuntu.Ubuntu_16_04())
# register_vm(ubuntu.Ubuntu_17_10())


VM_BASE_DIR = os.path.abspath(
    os.path.join(os.path.join(os.path.dirname(__file__), '..'), 'vmtests'))


class TestSettings(object):
    def __init__(self, args):
        self.branch = args.branch
        self.source = args.source
        self.rebuild_vm = args.rebuild_vm
        self.just_start = args.just_start
        self.clean_snapshot = args.clean_snapshot
        self.shutdown = args.shutdown


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


async def main(event_loop, argv):
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        default='critical',
        help="Minimum level for log messages written to STDERR.")
    argparser.add_argument('--source', type=str, choices=['local', 'git'], default='local')
    argparser.add_argument('--branch', type=str, default='master')
    argparser.add_argument(
        '--rebuild-vm', type=bool_arg, default=False,
        help="Rebuild the VM from scratch, discarding the current state.")
    argparser.add_argument(
        '--clean-snapshot', type=bool_arg, default=True,
        help=("Restore the VM from the 'clean' snapshot (which was created after the VM has"
              " been setup) before running the tests."))
    argparser.add_argument(
        '--just-start', type=bool_arg, default=False,
        help=("Just start the VM in the current state (not restoring the clean snapshot)"
              " and don't run the tests."))
    argparser.add_argument(
        '--shutdown', type=bool_arg, default=True,
        help="Shut the VM down after running the tests.")
    argparser.add_argument('vms', nargs='*')
    args = argparser.parse_args(argv[1:])

    # if not args.vms:
    #     args.vms = list(sorted(VMs.keys()))

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

    settings = TestSettings(args)

    vm = testvm.Ubuntu_16_04(name='ubuntu-16.04', base_dir=VM_BASE_DIR, event_loop=event_loop)
    vm = testvm.Ubuntu_18_04(name='ubuntu-18.04', base_dir=VM_BASE_DIR, event_loop=event_loop)
    #vm = testvm.Debian9(name='debian-9', base_dir=VM_BASE_DIR, event_loop=event_loop)
    await vm.install()
    await vm.start(gui=True)
    try:
        await vm.wait_for_state(vm.POWEROFF, timeout=3600)
    finally:
        await vm.poweroff()

    # results = {}
    # for _, vm in sorted(VMs.items()):
    #     if vm.name in args.vms:
    #         results[vm.name] = vm.runtest(settings)

    # if not all(results.values()):
    #     print()
    #     print('-' * 96)
    #     print("%d/%d tests FAILED." % (
    #         sum(1 for success in results.values() if not success), len(results)))

    #     for vm, success in sorted(results.items(), key=lambda i: i[0]):
    #         print("%s... %s" % (vm, 'SUCCESS' if success else 'FAILED'))

    #     return 1

    return 0


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    sys.exit(loop.run_until_complete(main(loop, sys.argv)))
