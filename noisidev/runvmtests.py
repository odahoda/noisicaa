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
import datetime
import glob
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

cat >~/.pip/pip.conf <<EOF
[global]
index-url = http://_gateway:{settings.devpi_port}/root/pypi/+simple/
trusted-host = _gateway
EOF

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
sudo ./waf install

./waf configure --venvdir=../venv --download --install-system-packages --enable-tests
./waf build
./waf test --tags=unit
'''


async def log_dumper(fp_in, out_func, encoding=None):
    if encoding is None:
        line = ''
        lf = '\n'
    else:
        line = bytearray()
        lf = b'\n'

    while not fp_in.at_eof():
        c = await fp_in.read(1)
        if c == lf:
            if encoding is not None:
                line = line.decode(encoding)
            out_func(line)
            if encoding is None:
                line = ''
            else:
                line = bytearray()

        else:
            line += c

    if line:
        if encoding is not None:
            line = line.decode(encoding)
        out_func(buf)


class TestMixin(testvm.VM):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__installed_sentinel = os.path.join(self.vm_dir, 'installed')

    @property
    def is_installed(self):
        return os.path.isfile(self.__installed_sentinel)

    async def __spinner(self, prefix, result):
        start_time = datetime.datetime.now()
        spinner = '-\|/'
        spinner_idx = 0
        while True:
            duration = (datetime.datetime.now() - start_time).total_seconds()
            minutes = duration // 60
            seconds = duration - 60 * minutes
            sys.stdout.write('\033[2K\r%s [%02d:%02d] ... ' % (prefix, minutes, seconds))
            if not result.empty():
                sys.stdout.write(await result.get())
                sys.stdout.write('\n')
                break

            sys.stdout.write('(%s)' % spinner[spinner_idx])
            spinner_idx = (spinner_idx + 1) % len(spinner)
            sys.stdout.flush()
            await asyncio.sleep(0.2, loop=self.event_loop)

    async def install(self):
        logger.info("Installing VM '%s'...", self.name)

        result = asyncio.Queue(loop=self.event_loop)
        spinner_task = self.event_loop.create_task(self.__spinner("Installing VM '%s'" % self.name, result))
        try:
            if os.path.isfile(self.__installed_sentinel):
                os.unlink(self.__installed_sentinel)
            for img_path in glob.glob(os.path.join(self.vm_dir, '*.img')):
                os.unlink(img_path)
            await super().install()
            await self.create_snapshot('clean')
            open(self.__installed_sentinel, 'w').close()
        except:
            logger.error("Installation of VM '%s' failed.", self.name)
            result.put_nowait('FAILED')
            raise
        else:
            logger.info("Installed VM '%s'...", self.name)
            result.put_nowait('OK')
        finally:
            await spinner_task

    async def run_test(self, settings):
        logger.info("Running test '%s'... ", self.name)

        result = asyncio.Queue(loop=self.event_loop)
        spinner_task = self.event_loop.create_task(self.__spinner("Running test '%s'" % self.name, result))
        try:
            await self.do_test(settings)
        except Exception as exc:
            logger.error("Test '%s' failed with an exception:\n%s", self.name, traceback.format_exc())
            result.put_nowait('FAILED')
            return False
        else:
            logger.info("Test '%s' completed successfully.")
            result.put_nowait('SUCCESS')
            return True
        finally:
            await spinner_task

    async def do_test(self, settings):
        vm_logger = logging.getLogger(self.name)

        logger.info("Waiting for SSH port to open...")
        await self.wait_for_ssh()

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

            proc = await client.create_process("./runtest.sh", stderr=subprocess.STDOUT)
            stdout_dumper = self.event_loop.create_task(log_dumper(proc.stdout, vm_logger.info))
            await proc.wait()
            await stdout_dumper
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
        self.shutdown = args.shutdown
        self.devpi_port = args.devpi_port


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
        '--force-install', action="store_true", default=False,
        help="Force reinstallation of operating system before starting VM.")
    argparser.add_argument(
        '--cores', type=int,
        default=min(4, len(os.sched_getaffinity(0))),
        help="Number of emulated cores in the VM.")
    argparser.add_argument(
        '--devpi-port', type=int,
        default=18000,
        help="Local port for devpi server.")
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
    formatter = logging.Formatter(
        '%(relativeCreated)8d:%(levelname)-8s:%(name)s: %(message)s')

    root_logger.setLevel(logging.DEBUG)

    log_path = os.path.join(VM_BASE_DIR, time.strftime('debug-%Y%m%d-%H%M%S.log'))
    current_log_path = os.path.join(VM_BASE_DIR, 'debug.log')
    if os.path.isfile(current_log_path) or os.path.islink(current_log_path):
        os.unlink(current_log_path)
    os.symlink(log_path, current_log_path)

    handler = logging.FileHandler(log_path, 'w')
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(
        {'debug': logging.DEBUG,
         'info': logging.INFO,
         'warning': logging.WARNING,
         'error': logging.ERROR,
         'critical': logging.CRITICAL,
        }[args.log_level])
    root_logger.addHandler(handler)

    try:
        logger.info(' '.join(argv))

        devpi_logger = logging.getLogger('devpi')
        devpi_serverdir = os.path.join(ROOT_DIR, 'vmtests', '_cache', 'devpi')
        if not os.path.isdir(devpi_serverdir):
            logger.info("Initializing devpi cache at '%s'...", devpi_serverdir)
            devpi = await asyncio.create_subprocess_exec(
                'devpi-server',
                '--serverdir=%s' % devpi_serverdir,
                '--init',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                loop=event_loop)
            devpi_stdout_dumper = event_loop.create_task(log_dumper(devpi.stdout, devpi_logger.debug, encoding='utf-8'))
            await devpi.wait()
            await devpi_stdout_dumper

        logger.info("Starting local devpi server on port %d...", args.devpi_port)
        devpi = await asyncio.create_subprocess_exec(
            'devpi-server',
            '--serverdir=%s' % devpi_serverdir,
            '--port=%d' % args.devpi_port,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            loop=event_loop)
        devpi_stdout_dumper = event_loop.create_task(log_dumper(devpi.stdout, devpi_logger.debug, encoding='utf-8'))
        try:
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

                if args.force_install:
                    await vm.install()

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

                if args.force_install:
                    await vm.install()

                assert vm.is_installed
                try:
                    await vm.start(gui=args.gui if args.gui is not None else False)
                    await vm.wait_for_ssh()

                    proc = await asyncio.create_subprocess_exec(
                        '/usr/bin/sshpass', '-p123',
                        '/usr/bin/ssh',
                        '-p5555',
                        '-X',
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

                if not vm.is_installed or args.force_install:
                    await vm.install()

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

        finally:
            devpi.terminate()
            await devpi.wait()
            await devpi_stdout_dumper

    except:
        logger.error("runvmtests failed with an exception:\n%s", traceback.format_exc())
        raise

    finally:
        print("Full logs at %s" % log_path)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    sys.exit(loop.run_until_complete(main(loop, sys.argv)))
