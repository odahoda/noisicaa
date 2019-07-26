#!/usr/bin/python3

import asyncio
import functools
import json
import logging
import os
import os.path
import pprint
import random
import re
import shutil
import subprocess
import socket
import sys
import tempfile
import time
import traceback
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


class QmpProtocol(asyncio.Protocol):
    def __init__(self, event_loop, response_queue):
        super().__init__()

        self.__event_loop = event_loop
        self.__response_queue = response_queue
        self.__transport = None
        self.__buffer = bytearray()
        self.__ready = asyncio.Event(loop=self.__event_loop)

    async def wait(self):
        await self.__ready.wait()

    def connection_made(self, transport):
        logger.info("QMP connection started")
        self.__transport = transport

    def connection_lost(self, exc):
        logger.info("QMP connection lost: %s", exc)

    def data_received(self, data):
        logger.debug("QMP data received: %r", data)
        self.__buffer += data

        while True:
            eol = self.__buffer.find(b'\r\n')
            if eol < 0:
                break

            response_json = self.__buffer[:eol]
            del self.__buffer[:eol+2]

            response = json.loads(response_json)

            if 'return' in response:
                if not self.__ready.is_set():
                    logger.info("QMP negotiation complete: %s", response['return'])
                    self.__ready.set()
                else:
                    self.__response_queue.put_nowait(response)
            elif 'error' in response:
                if not self.__ready.is_set():
                    logger.error("QMP negotiation failed: %s", response['error'])
                else:
                    self.__response_queue.put_nowait(response)
            elif 'event' in response:
                logger.info("QMP event:\n%s", pprint.pformat(response))
            elif 'QMP' in response:
                logger.info("QMP greeting:\n%s", pprint.pformat(response))
                self.__transport.write(b'{ "execute": "qmp_capabilities" }')
            else:
                logger.error("Unhandled QMP response:\n%s", pprint.pformat(response))


class VM(object):
    # VM states
    POWEROFF = 'poweroff'
    RUNNING = 'running'

    def __init__(self, *, name, base_dir, event_loop, cores=1, memory=1 << 30, disk_size=10 << 30):
        self.name = name
        self.base_dir = base_dir
        self.event_loop = event_loop

        self.vm_dir = os.path.join(base_dir, self.name)
        self.installed_sentinel = os.path.join(self.vm_dir, 'installed')

        self.__cores = cores
        self.__memory = memory
        self.__disk_size = disk_size
        self.__iso_path = None

        self.__qproc = None
        self.__qproc_wait_task = None
        self.__qproc_stdout_task = None
        self.__qproc_stderr_task = None
        self.__qmp_socket_path = None
        self.__qmp_transport = None
        self.__qmp_protocol = None
        self.__qmp_response_queue = None

        self.__state = self.POWEROFF
        self.__state_cond = asyncio.Condition(loop=self.event_loop)

    @property
    def __hd_path(self):
        return os.path.join(self.vm_dir, 'current.img')

    @property
    def state(self):
        return self.__state

    async def __set_state(self, state):
        async with self.__state_cond:
            self.__state = state
            self.__state_cond.notify_all()

    async def wait_for_state(self, state, *, timeout):
        deadline = time.time() + timeout
        async with self.__state_cond:
            while self.__state != state:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError("State '%s' not reached (currently: '%s')" % (state, self.state))
                try:
                    await asyncio.wait_for(
                        self.__state_cond.wait(), timeout=remaining, loop=self.event_loop)
                except asyncio.TimeoutError:
                    pass


    async def start(self, *, gui=True):
        assert self.__qproc is None

        self.__qmp_socket_path = os.path.join(tempfile.gettempdir(), 'vmtests-qmp.%08x.sock' % random.getrandbits(31))

        cmdline = []
        cmdline.append('/usr/bin/qemu-system-x86_64')
        cmdline.extend(['--enable-kvm'])
        cmdline.extend(['-m', '%dM' % (self.__memory // (1<<20))])
        cmdline.extend(['-smp', '%d' % self.__cores])
        cmdline.extend(['-device', 'e1000,netdev=net0',
                        '-netdev', 'user,id=net0,hostfwd=tcp::5555-:22'])
        cmdline.extend(['--drive', 'format=qcow2,file=%s' % self.__hd_path])
        if self.__iso_path is not None:
            cmdline.extend(['--drive', 'media=cdrom,file=%s,readonly' % self.__iso_path])
        cmdline.extend(['-qmp', 'unix:%s,server,nowait' % self.__qmp_socket_path])
        if gui:
            cmdline.extend(['-display', 'sdl'])
        else:
            cmdline.extend(['-display', 'none'])

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

        self.__qmp_response_queue = asyncio.Queue(loop=self.event_loop)
        deadline = time.time() + 60
        while True:
            if os.path.exists(self.__qmp_socket_path):
                try:
                    self.__qmp_transport, self.__qmp_protocol = await self.event_loop.create_unix_connection(
                        functools.partial(QmpProtocol, self.event_loop, self.__qmp_response_queue),
                        self.__qmp_socket_path)
                except OSError as exc:
                    logger.debug("Failed to connect to QMP socket: %s", exc)
                else:
                    logger.info("Connected to QMP socket.")
                    break

            if time.time() > deadline:
                raise TimeoutError("Failed to connect to QMP socket")
            await asyncio.sleep(0.5, loop=self.event_loop)

        await asyncio.wait_for(self.__qmp_protocol.wait(), timeout=10)

        self.__qproc_wait_task = self.event_loop.create_task(self.__qproc.wait())
        self.__qproc_wait_task.add_done_callback(self.__qproc_finished)

        await self.__set_state(self.RUNNING)

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
        self.__qmp_transport = None
        self.__qmp_protocol = None
        self.event_loop.create_task(self.__set_state(self.POWEROFF))

    async def __qmp_execute(self, cmd, *, timeout=10):
        logger.info("Sending QMP command '%s'...", cmd)
        self.__qmp_transport.write(json.dumps({'execute': cmd}).encode('utf-8') + b'\r\n')
        response = await asyncio.wait_for(self.__qmp_response_queue.get(), timeout=timeout)
        if 'error' in response:
            raise RuntimeError("QMP command '%s' failed: %s", cmd, pprint.pformat(response['error']))
        logger.info("QMP command '%s' result: %s", cmd, response['return'])
        return response['return']

    async def poweroff(self, *, timeout=300):
        if self.__qmp_transport is not None:
            try:
                await self.__qmp_execute('system_powerdown')
                await self.wait_for_state(self.POWEROFF, timeout=timeout)
            except asyncio.TimeoutError:
                pass

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

        if self.__qmp_socket_path is not None and os.path.exists(self.__qmp_socket_path):
            os.unlink(self.__qmp_socket_path)

        self.__qproc_wait_task = None
        self.__qproc_stdout_task = None
        self.__qproc_stderr_task = None
        self.__qmp_socket_path = None
        self.__qmp_transport = None
        self.__qmp_protocol = None
        self.__qmp_response_queue = None

    async def create_snapshot(self, name='clean'):
        assert self.state == self.POWEROFF
        assert os.path.isfile(self.__hd_path)
        snapshot_path = os.path.join(os.path.dirname(self.__hd_path), '%s.img' % name)
        assert not os.path.isfile(snapshot_path)

        os.rename(self.__hd_path, snapshot_path)
        cmd = [
            '/usr/bin/qemu-img', 'create',
            '-f', 'qcow2',
            '-b', snapshot_path,
            self.__hd_path,
        ]
        logger.info("Running command %s", ' '.join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            loop=self.event_loop)
        self.event_loop.create_task(
            self.__qproc_logger(proc.stdout, logger.info))
        self.event_loop.create_task(
            self.__qproc_logger(proc.stderr, logger.warning))
        await proc.wait()

    async def restore_snapshot(self, name='clean'):
        assert self.state == self.POWEROFF
        assert os.path.isfile(self.__hd_path)
        snapshot_path = os.path.join(os.path.dirname(self.__hd_path), '%s.img' % name)
        assert os.path.isfile(snapshot_path)

        os.unlink(self.__hd_path)
        cmd = [
            '/usr/bin/qemu-img', 'create',
            '-f', 'qcow2',
            '-b', snapshot_path,
            self.__hd_path,
        ]
        logger.info("Running command %s", ' '.join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            loop=self.event_loop)
        self.event_loop.create_task(
            self.__qproc_logger(proc.stdout, logger.info))
        self.event_loop.create_task(
            self.__qproc_logger(proc.stderr, logger.warning))
        await proc.wait()

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
        assert self.state == self.POWEROFF
        assert self.__iso_path is None

        self.__iso_path = path

    async def detach_iso(self):
        assert self.state == self.POWEROFF
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
