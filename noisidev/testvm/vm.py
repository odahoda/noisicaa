#!/usr/bin/python3

import asyncio
import logging
import os
import os.path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class VM(object):
    # VM states
    POWEROFF = 'poweroff'
    RUNNING = 'running'

    def __init__(self, *, name, base_dir, event_loop):
        self.name = name
        self.base_dir = base_dir
        self.event_loop = event_loop

        self.vm_dir = os.path.join(base_dir, self.name)
        self.installed_sentinel = os.path.join(self.vm_dir, 'installed')

        self.__memory = 1 << 30  # 1G
        self.__disk_size = 10 << 30  # 10G
        self.__iso_path = None

        self.__qproc = None
        self.__qproc_wait_task = None
        self.__qproc_stdout_task = None
        self.__qproc_stderr_task = None

    @property
    def __hd_path(self):
        return os.path.join(self.vm_dir, 'disk.img')

    @property
    def state(self):
        if self.__qproc is not None:
            return self.RUNNING
        return self.POWEROFF

    async def wait_for_state(self, state, *, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.state == state:
                return
            await asyncio.sleep(5)
        raise TimeoutError("State '%s' not reached (currently: '%s')" % (state, self.state))

    async def start(self, *, gui=True):
        assert self.__qproc is None

        cmdline = []
        cmdline.append('/usr/bin/qemu-system-x86_64')
        cmdline.extend(['--enable-kvm'])
        cmdline.extend(['-m', '%dM' % (self.__memory // (1<<20))])
        cmdline.extend(['-device', 'e1000,netdev=net0',
                        '-netdev', 'user,id=net0,hostfwd=tcp::5555-:22'])
        cmdline.extend(['--drive', 'format=qcow2,file=%s' % self.__hd_path])
        if self.__iso_path is not None:
            cmdline.extend(['--drive', 'media=cdrom,file=%s,readonly' % self.__iso_path])

        logger.info("Starting QEmu VM: %s", ' '.join(cmdline))
        self.__qproc = await asyncio.create_subprocess_exec(
            *cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            loop=self.event_loop)

        self.__qproc_stdout_task = self.event_loop.create_task(
            self.__qproc_logger(self.__qproc.stdout, logger.info))
        self.__qproc_stdout_task = self.event_loop.create_task(
            self.__qproc_logger(self.__qproc.stderr, logger.warning))

        self.__qproc_wait_task = self.event_loop.create_task(self.__qproc.wait())
        self.__qproc_wait_task.add_done_callback(self.__qproc_finished)

    async def __qproc_logger(self, fp, log):
        while True:
            lineb = await fp.readline()
            if not lineb:
                break
            line = lineb.decode('utf-8', 'backslashreplace')
            line = line.rstrip('\r\n')
            log(line)

    def __qproc_finished(self, task):
        assert self.__qproc.returncode is not None

        logger.info("QEmu VM finished (rc=%d).", self.__qproc.returncode)

        self.__qproc = None

    async def poweroff(self, *, timeout=300):
        if self.__qproc:
            self.__qproc.terminate()

        tasks = []
        if self.__qproc_wait_task is not None:
            tasks.append(self.__qproc_wait_task)
        if self.__qproc_stdout_task is not None:
            tasks.append(self.__qproc_stdout_task)
        if self.__qproc_stderr_task is not None:
            tasks.append(self.__qproc_stderr_task)

        if tasks:
            done, pending = await asyncio.wait(tasks, loop=self.event_loop)
            assert not pending
            for task in done:
                task.result()

        self.__qproc_wait_task = None
        self.__qproc_stdout_task = None
        self.__qproc_stderr_task = None

    async def create_snapshot(self, name='clean'):
        raise NotImplementedError

    async def restore_snapshot(self, name='clean'):
        raise NotImplementedError

    def download_file(self, url, path):
        logging.info("Downloading '%s' to '%s'...", url, path)
        total_bytes = 0
        with urllib.request.urlopen(url) as fp_in:
            with open(path + '.partial', 'wb') as fp_out:
                last_report = time.time()
                try:
                    while True:
                        dat = fp_in.read(10240)
                        if not dat:
                            break
                        fp_out.write(dat)
                        total_bytes += len(dat)
                        if time.time() - last_report > 1:
                            sys.stderr.write(
                                'Downloading %s: %d bytes\r'
                                % (url, total_bytes))
                            sys.stderr.flush()
                            last_report = time.time()
                finally:
                    sys.stderr.write('\033[K')
                    sys.stderr.flush()

        os.rename(path + '.partial', path)
        print('Downloaded %s: %d bytes' % (url, total_bytes))

    def get_default_if(self):
        proc = subprocess.run(['route', '-n'], check=True, stdout=subprocess.PIPE)
        for line in proc.stdout.decode('utf-8').splitlines():
            if line.startswith('0.0.0.0'):
                return line.split()[-1]

        raise RuntimeError

    async def delete(self):
        raise NotImplementedError

    async def setup_vm(self):
        if not os.path.exists(self.__hd_path):
            cmd = [
                '/usr/bin/qemu-img', 'create',
                '-f', 'qcow2',
                self.__hd_path, str(self.__disk_size),
            ]
            logger.info("Running command %s", ' '.join(cmd))
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                loop=self.event_loop)
            await proc.wait()

    async def attach_iso(self, path):
        assert self.__qproc is None
        assert self.__iso_path is None

        self.__iso_path = path

    async def detach_iso(self):
        assert self.__qproc is None
        assert self.__iso_path is not None

        self.__iso_path = None

    @property
    def is_installed(self):
        return os.path.isfile(self.installed_sentinel)

    async def install(self):
        if not self.is_installed:
            if not os.path.isdir(self.vm_dir):
                os.makedirs(self.vm_dir)

            logger.info("Setting up VM %s...", self.name)
            await self.setup_vm()
            logger.info("Setup complete.")

            logger.info("Installing VM %s...", self.name)
            await self.do_install()
            logger.info("Installation complete.")

            open(self.installed_sentinel, 'w').close()

    async def do_install(self):
        raise NotImplementedError
