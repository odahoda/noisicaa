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
import subprocess
import sys
import time
import traceback

import asyncssh

from . import testvm

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.join(os.path.dirname(__file__), '..')))


TEST_SCRIPT = r'''#!/bin/bash

SOURCE="{settings.source}"
BRANCH="{settings.branch}"

set -e
set -x

sudo apt-get -q -y install python3 python3-venv

rm -fr noisicaa/

if [ $SOURCE == git ]; then
  sudo apt-get -q -y install git
  git clone --branch=$BRANCH --single-branch https://github.com/odahoda/noisicaa
elif [ $SOURCE == local ]; then
  mkdir noisicaa/
  tar -x -z -Cnoisicaa/ -flocal.tar.gz
fi

cd noisicaa/

./waf configure --venvdir=../venv --download --install-system-packages
./waf build

./waf configure --venvdir=../venv --download --install-system-packages --enable-tests
./waf build
./waf test --tags=unit
'''


class TestMixin(testvm.VM):
    async def run_test(self, settings):
        sys.stdout.write("Running test '%s'... " % self.name)
        sys.stdout.flush()
        try:
            await self.do_test(settings)
        except Exception as exc:
            sys.stdout.write('\n')
            traceback.print_exc()
            return False
        else:
            sys.stdout.write('SUCCESS\n')
            return True

    async def do_test(self, settings):
        logger.info("Waiting for SSH port to open...")

        import socket

        deadline = time.time() + 300
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect(('localhost', 5555))
                    s.sendall(b'Hello, world')
                    logger.info("ok")
            except socket.timeout as exc:
                logger.debug("Failed to connect: %s", exc)
                if time.time() > deadline:
                    raise TimeoutError("Failed to connect to VM")
            else:
                break

        logger.info("Connecting to VM...")
        client = await asyncssh.connect(
            host='localhost',
            port=5555,
            options=asyncssh.SSHClientConnectionOptions(
                username='testuser',
                password='123',
                known_hosts=None),
            loop=self.event_loop)
        try:
            sftp = await client.start_sftp_client()
            try:
                logger.info("Copy runtest.sh...")
                async with sftp.open('runtest.sh', 'w') as fp:
                    await fp.write(TEST_SCRIPT.format(settings=settings))
                await sftp.chmod('runtest.sh', 0o775)

                if settings.source == 'local':
                    logger.info("Copy local.tar.gz...")
                    proc = subprocess.Popen(
                        ['git', 'config', 'core.quotepath', 'off'],
                        cwd=ROOT_DIR)
                    proc.wait()
                    assert proc.returncode == 0

                    proc = subprocess.Popen(
                        ['bash', '-c', 'tar -c -z -T<(git ls-tree --full-tree -r --name-only HEAD) -f-'],
                        cwd=ROOT_DIR,
                        stdout=subprocess.PIPE)
                    async with sftp.open('local.tar.gz', 'wb') as fp:
                        while True:
                            buf = proc.stdout.read(1024)
                            if not buf:
                                break
                            await fp.write(buf)
                    proc.wait()
                    assert proc.returncode == 0

            finally:
                sftp.exit()

            proc = await client.create_process("./runtest.sh")
            async def dumper(fp_in, fp_out):
                while not fp_in.at_eof():
                    fp_out.write(await fp_in.readline())
            stdout_dumper = self.event_loop.create_task(dumper(proc.stdout, sys.stdout))
            stderr_dumper = self.event_loop.create_task(dumper(proc.stderr, sys.stderr))
            await proc.wait()
            await stdout_dumper
            await stderr_dumper
            assert proc.returncode == 0

        finally:
            client.close()


class Ubuntu_16_04(TestMixin, testvm.Ubuntu_16_04):
    pass

class Ubuntu_18_04(TestMixin, testvm.Ubuntu_18_04):
    pass


ALL_VMTESTS = {
    'ubuntu-16.04': Ubuntu_16_04,
    'ubuntu-18.04': Ubuntu_18_04,
}

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
        '--just-start', action='store_true', default=False,
        help=("Just start the VM in the current state (not restoring the clean snapshot)"
              " and don't run the tests."))
    argparser.add_argument(
        '--login', action='store_true', default=False,
        help=("Start the VM in the current state (not restoring the clean snapshot)"
              " and open a shell session. The VM is powered off when the shell is closed."))
    argparser.add_argument(
        '--shutdown', type=bool_arg, default=True,
        help="Shut the VM down after running the tests.")
    argparser.add_argument(
        '--gui', type=bool_arg, default=None,
        help="Force showing/hiding the UI.")
    argparser.add_argument(
        '--cores', type=int, default=len(os.sched_getaffinity(0)),
        help="Number of emulated cores in the VM.")
    argparser.add_argument('vms', nargs='*')
    args = argparser.parse_args(argv[1:])

    if not args.vms:
        args.vms = list(sorted(ALL_VMTESTS.keys()))

    for vm_name in args.vms:
        if vm_name not in ALL_VMTESTS:
            raise ValueError("'%s' is not a valid test name" % vm_name)

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

    vm_args = {
        'base_dir': VM_BASE_DIR,
        'event_loop': event_loop,
        'cores': args.cores,
        'memory': 2 << 30,
    }
    if args.just_start:
        assert len(args.vms) == 1

        vm_name = args.vms[0]
        vm_cls = ALL_VMTESTS[vm_name]
        vm = vm_cls(name=vm_name, **vm_args)

        assert vm.is_installed
        try:
            await vm.start(gui=args.gui if args.gui is not None else True)
            await vm.wait_for_state(vm.POWEROFF, timeout=3600)
        finally:
            await vm.poweroff()

        return

    if args.login:
        assert len(args.vms) == 1

        vm_name = args.vms[0]
        vm_cls = ALL_VMTESTS[vm_name]
        vm = vm_cls(name=vm_name, **vm_args)

        assert vm.is_installed
        try:
            await vm.start(gui=args.gui if args.gui is not None else False)
            await vm.wait_for_ssh()

            proc = await asyncio.create_subprocess_exec(
                '/usr/bin/sshpass', '-p123',
                '/usr/bin/ssh',
                '-p5555',
                '-oStrictHostKeyChecking=off',
                '-oUserKnownHostsFile=/dev/null',
                '-oLogLevel=quiet',
                'testuser@localhost',
                loop=event_loop)
            await proc.wait()

        finally:
            await vm.poweroff()

        return

    results = {}
    for vm_name in args.vms:
        vm_cls = ALL_VMTESTS[vm_name]
        vm = vm_cls(name=vm_name, **vm_args)

        if not vm.is_installed:
            await vm.install()
            await vm.create_snapshot('clean')

        elif args.clean_snapshot:
            await vm.restore_snapshot('clean')

        try:
            await vm.start(gui=args.gui if args.gui is not None else False)
            results[vm.name] = await vm.run_test(settings)

        finally:
            await vm.poweroff()

    if not all(results.values()):
        print()
        print('-' * 96)
        print("%d/%d tests FAILED." % (
            sum(1 for success in results.values() if not success), len(results)))
        print()

        for vm, success in sorted(results.items(), key=lambda i: i[0]):
            print("%s... %s" % (vm, 'SUCCESS' if success else 'FAILED'))

        return 1

    return 0


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    sys.exit(loop.run_until_complete(main(loop, sys.argv)))
