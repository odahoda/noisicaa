#!/usr/bin/env python3

import argparse
import os
import os.path
import sys

from .vmtests import ubuntu_16_04

VMs = {}

def register_vm(vm):
    assert vm.name not in VMs
    VMs[vm.name] = vm

register_vm(ubuntu_16_04.Ubuntu_16_04())


class TestSettings(object):
    def __init__(self, args):
        self.branch = args.branch
        self.source = args.source
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
    argparser.add_argument('--deletevm', type=str, default=None)
    argparser.add_argument('--source', type=str, choices=['local', 'git'], default='local')
    argparser.add_argument('--branch', type=str, default='master')
    argparser.add_argument('--clean-snapshot', type=bool_arg, default=True)
    argparser.add_argument('--shutdown', type=bool_arg, default=True)
    args = argparser.parse_args(argv[1:])

    if args.deletevm is not None:
        try:
            vm = VMs[args.deletevm]
        except KeyError:
            print("Invalid distribution name.")
            return 1

        vm.delete()
        return 0

    settings = TestSettings(args)

    results = {}
    for _, vm in sorted(VMs.items()):
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
