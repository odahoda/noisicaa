#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import os
import os.path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
import urllib.parse
import urllib.request

# import paramiko

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
VM_BASE_DIR = os.path.join(ROOT_DIR, 'vmtests')

class VM(object):
    # VM states
    POWEROFF = 'poweroff'
    RUNNING = 'running'

    def __init__(self, name):
        self.name = name
        self.vm_dir = os.path.join(VM_BASE_DIR, self.name)
        self.installed_sentinel = os.path.join(self.vm_dir, 'installed')

    def get_ip(self, *, timeout):
        state = self.get_state()
        if state != self.RUNNING:
            raise RuntimeError("VM not running (current state: '%s')" % state)

        msg = False
        deadline = time.time() + timeout
        while time.time() < deadline:
            ip = self.get_guest_property('/VirtualBox/GuestInfo/Net/0/V4/IP')
            if ip is not None:
                return ip
            if not msg:
                print("Waiting for IP address...")
                msg = True
            time.sleep(5)

        raise TimeoutError("Timed out waiting for IP address.")

    def is_registered(self):
        for line in self.vboxmanage('list', 'vms', echo_cmd=False, get_output=True).splitlines():
            m = re.match(r'^"([^"]+)" {[-0-9a-f]+}$', line.strip())
            if m and m.group(1) == self.name:
                return True

        return False

    def get_guest_property(self, prop):
        value = None
        for line in self.vboxmanage(
                'guestproperty', 'get', self.name, prop,
                echo_cmd=False, get_output=True).splitlines():
            if line.startswith('Value:'):
                value = line.split(':')[1].strip()
        return value

    def get_vm_info(self):
        vm_info = {}
        for line in self.vboxmanage(
                'showvminfo', self.name, '--machinereadable',
                echo_cmd=False, get_output=True).splitlines():
            key, value = line.split('=', 1)
            if value.startswith('"') and value.endswith('"'):
                value = value.strip('"')
            elif re.match(r'^\d+$', value):
                value = int(value)

            vm_info[key] = value

        return vm_info

    def get_state(self):
        return self.get_vm_info()['VMState']

    def start_vm(self):
        self.vboxmanage(
            'startvm', self.name,
            '--type', 'gui'
        )

    def wait_for_state(self, state, *, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.get_state() == state:
                return
            time.sleep(5)
        raise TimeoutError("State '%s' not reached (currently: '%s')" % (state, self.get_state()))

    def download_file(self, url, path):
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

    def vboxmanage(self, *args, get_output=False, echo_cmd=True):
        argv = ['vboxmanage']
        argv.extend(args)

        # Tweak $HOME to create a separate "VirtualBox installation", and we don't mess up the
        # users VirtualBox config.
        env = dict(**os.environ)
        env['HOME'] = VM_BASE_DIR

        if echo_cmd:
            print(' '.join(argv))

        if get_output:
            proc = subprocess.run(argv, check=True, env=env, stdout=subprocess.PIPE)
            return proc.stdout.decode('utf-8')
        else:
            subprocess.run(argv, check=True, env=env)

    def get_default_if(self):
        proc = subprocess.run(['route', '-n'], check=True, stdout=subprocess.PIPE)
        for line in proc.stdout.decode('utf-8').splitlines():
            if line.startswith('0.0.0.0'):
                return line.split()[-1]

        raise RuntimeError

    def delete(self):
        if self.is_registered():
            self.vboxmanage('unregistervm', self.name)

        if os.path.isdir(self.vm_dir):
            print("rm -fr %s" % self.vm_dir)
            shutil.rmtree(self.vm_dir)

    def setup_vm(self):
        vm_cfg_path = os.path.join(self.vm_dir, '%s.vbox' % self.name)
        if not os.path.isfile(vm_cfg_path):
            self.vboxmanage(
                'createvm',
                '--register',
                '--name', self.name,
                '--basefolder', VM_BASE_DIR,
            )
            self.vboxmanage(
                'modifyvm', self.name,
                '--memory', '1024',  # 1G
                '--cpus', '2',
                '--nic1', 'bridged',
                '--bridgeadapter1', self.get_default_if(),
                '--audio', 'alsa',
            )
            self.vboxmanage(
                'storagectl', self.name,
                '--name', 'ctrl0',
                '--add', 'ide',
                '--controller', 'PIIX4',
                '--portcount', '2',
                '--bootable', 'on',
            )

    def setup_hd(self):
        hd_path = os.path.join(self.vm_dir, 'disk.img')

        if not os.path.isfile(hd_path):
            self.vboxmanage(
                'createmedium', 'disk',
                '--filename', hd_path,
                '--size', '10240',  # 10G
            )
            self.vboxmanage(
                'storageattach', self.name,
                '--storagectl', 'ctrl0',
                '--port', '0',
                '--device', '0',
                '--type', 'hdd',
                '--medium', hd_path,
            )

    def attach_iso(self, path):
        self.vboxmanage(
            'storageattach', self.name,
            '--storagectl', 'ctrl0',
            '--port', '1',
            '--device', '0',
            '--type', 'dvddrive',
            '--medium', path,
        )

    def detach_iso(self):
        self.vboxmanage(
            'storageattach', self.name,
            '--storagectl', 'ctrl0',
            '--port', '1',
            '--device', '0',
            '--type', 'dvddrive',
            '--medium', 'emptydrive',
        )

    def install(self):
        if not os.path.isfile(self.installed_sentinel):
            print("Installing VM %s..." % self.name)

            if not os.path.isdir(self.vm_dir):
                os.makedirs(self.vm_dir)

            self.setup_vm()
            self.setup_hd()

            self.do_install()

            self.vboxmanage(
                'snapshot', self.name,
                'take', 'clean',
            )

            open(self.installed_sentinel, 'w').close()

    def do_install(self):
        raise NotImplementedError

    def runtest(self, settings):
        try:
            self.install()

            if settings.clean_snapshot:
                self.vboxmanage(
                    'snapshot', self.name,
                    'restore', 'clean',
                )
            self.vboxmanage(
                'startvm', self.name,
                '--type', 'gui'
            )
            return self.do_test(settings)

        except Exception:  # pylint: disable=broad-except
            traceback.print_exc()
            return False

        finally:
            if settings.shutdown:
                self.vboxmanage('controlvm', self.name, 'acpipowerbutton')
                try:
                    self.wait_for_state('poweroff', timeout=300)
                except TimeoutError:
                    self.vboxmanage('controlvm', self.name, 'poweroff')

    def do_test(self):
        raise NotImplementedError


class VMTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def cleanUp(self):
        shutil.rmtree(self.temp_dir)

    def test_download_file(self):
        vm = VM(name='test')

        path = os.path.join(self.temp_dir, 'file')
        vm.download_file('http://www.google.com/', path)
        self.assertTrue(os.path.isfile(path))


if __name__ == '__main__':
    unittest.main()
