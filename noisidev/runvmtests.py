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
import os
import os.path
import sys

from .vmtests import ubuntu

VMs = {}

def register_vm(vm):
    assert vm.name not in VMs
    VMs[vm.name] = vm

register_vm(ubuntu.Ubuntu_16_04())
register_vm(ubuntu.Ubuntu_17_10())


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


def main(argv):
    argparser = argparse.ArgumentParser()
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

    if not args.vms:
        args.vms = list(sorted(VMs.keys()))

    settings = TestSettings(args)

    results = {}
    for _, vm in sorted(VMs.items()):
        if vm.name in args.vms:
            results[vm.name] = vm.runtest(settings)

    if not all(results.values()):
        print()
        print('-' * 96)
        print("%d/%d tests FAILED." % (
            sum(1 for success in results.values() if not success), len(results)))

        for vm, success in sorted(results.items(), key=lambda i: i[0]):
            print("%s... %s" % (vm, 'SUCCESS' if success else 'FAILED'))

        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
