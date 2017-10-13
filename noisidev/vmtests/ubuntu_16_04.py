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
import shutil
import subprocess
import sys

import paramiko

from . import vm

PRESEED_TEMPLATE = r'''
### Localization
d-i debian-installer/locale string en_US.UTF-8
d-i localechooser/supported-locales multiselect en_US.UTF-8, de_DE.UTF-8
d-i console-setup/ask_detect boolean false
d-i keyboard-configuration/xkb-keymap select {keyboard_layout}

### Network configuration
d-i netcfg/choose_interface select auto
d-i netcfg/hostname string {hostname}
d-i netcfg/get_hostname string {hostname}
d-i netcfg/get_domain string unnamed
d-i hw-detect/load_firmware boolean true

### Mirror settings
d-i mirror/country string manual
d-i mirror/http/hostname string archive.ubuntu.com
d-i mirror/http/directory string /ubuntu
d-i mirror/http/proxy string

### Account setup
d-i passwd/root-login boolean false
d-i passwd/make-user boolean true
d-i passwd/user-fullname string Tester
d-i passwd/username string {username}
d-i passwd/user-password password {password}
d-i passwd/user-password-again password {password}
d-i user-setup/allow-password-weak boolean true
d-i user-setup/encrypt-home boolean false

### Clock and time zone setup
d-i clock-setup/utc boolean true
d-i time/zone string {timezone}
d-i clock-setup/ntp boolean true
d-i clock-setup/ntp-server string ntp.ubuntu.com

### Partitioning
d-i preseed/early_command string umount /media || true
d-i partman-auto/method string lvm
d-i partman-auto-lvm/guided_size string max
d-i partman-lvm/device_remove_lvm boolean true
d-i partman-lvm/confirm boolean true
d-i partman-lvm/confirm_nooverwrite boolean true
d-i partman-auto-lvm/new_vg_name string main
d-i partman-md/device_remove_md boolean true
d-i partman-md/confirm boolean true
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i partman-basicmethods/method_only boolean false

### Disk layout
d-i partman-auto/expert_recipe string         \
  boot-root ::                                \
    512 512 512 ext4                          \
      $primary{{ }}                             \
      $bootable{{ }}                            \
      method{{ format }} format{{ }}              \
      use_filesystem{{ }} filesystem{{ ext4 }}    \
      mountpoint{{ /boot }}                     \
    .                                         \
    1024 102400000 1000000000 ext4            \
      $lvmok{{ }}                               \
      method{{ format }} format{{ }}              \
      use_filesystem{{ }} filesystem{{ ext4 }}    \
      mountpoint{{ / }}                         \
      lv_name{{ root }}                         \
    .                                         \
    200% 200% 200% linux-swap                 \
      $lvmok{{ }}                               \
      method{{ swap }} format{{ }}                \
      lv_name{{ swap }}                         \
    .

### Base system installation
d-i base-installer/install-recommends boolean true
d-i base-installer/kernel/image string linux-generic

### Apt setup
d-i apt-setup/restricted boolean true
d-i apt-setup/universe boolean true
d-i apt-setup/backports boolean true
d-i apt-setup/use_mirror boolean false
d-i apt-setup/services-select multiselect security, updates
d-i apt-setup/security_host string security.ubuntu.com
d-i apt-setup/security_path string /ubuntu

### Package selection
d-i tasksel/first multiselect none
d-i pkgsel/include string openssh-server
d-i pkgsel/upgrade select full-upgrade
d-i pkgsel/update-policy select unattended-upgrades
d-i grub-installer/only_debian boolean true
d-i grub-installer/with_other_os boolean true

### Finishing up the installation
d-i debian-installer/splash boolean false
d-i cdrom-detect/eject boolean true
d-i preseed/late_command string \
  cp /rc.local /target/etc/rc.local

### Shutdown machine
d-i finish-install/reboot_in_progress note
d-i debian-installer/exit/poweroff boolean true
'''

RC_LOCAL_SCRIPT = r'''#!/bin/bash -e

if [ ! -f /post-install-done ]; then
  set -x
  echo >/etc/sudoers.d/testuser "testuser ALL=(ALL) NOPASSWD:ALL"
  apt-get -q -y install virtualbox-guest-utils

  # Do not start the guest utils as part of normal system init,
  # because there seems to be a race with the network config.
  update-rc.d virtualbox-guest-utils remove

  touch /post-install-done
  poweroff
fi

/etc/init.d/virtualbox-guest-utils start
'''

WRAP_SCRIPT = r'''#!/bin/bash

set -x
sudo apt-get -q -y install git python3.5 python3.5-venv python3-setuptools xterm

touch test.log
xterm -e tail -f test.log &
XTERMPID=$!

./runtest.sh >>test.log 2>&1 && echo "SUCCESS" || echo "FAILED"

kill $XTERMPID
'''

TEST_SCRIPT = r'''#!/bin/bash

SOURCE="{settings.source}"
BRANCH="{settings.branch}"

set -e
set -x

rm -fr noisicaa/

if [ $SOURCE == git ]; then
  git clone --branch=$BRANCH --single-branch https://github.com/odahoda/noisicaa
elif [ $SOURCE == local ]; then
  mkdir noisicaa/
  tar -x -z -Cnoisicaa/ -flocal.tar.gz
fi

cd noisicaa/

pyvenv-3.5 ENV
. ENV/bin/activate

sudo apt-get -q -y install $(cat requirements.ubuntu.pkgs | grep -vE '^\s*#' | grep -vE '^\s*$')
pip install -r requirements.txt
python3 setup.py build
bin/runtests --gdb=false
'''

class Ubuntu_16_04(vm.VM):
    def __init__(self):
        super().__init__(name='ubuntu-16.04')

        self.iso_url = (
            'http://archive.ubuntu.com/ubuntu/dists/xenial-updates/main/'
            'installer-amd64/current/images/netboot/mini.iso')

    def do_install(self):
        orig_iso_path = os.path.join(self.vm_dir, 'installer-orig.iso')
        iso_path = os.path.join(self.vm_dir, 'installer.iso')

        if not os.path.isfile(orig_iso_path):
            self.download_file(self.iso_url, orig_iso_path)

        if not os.path.isfile(iso_path):
            self.patch_iso(orig_iso_path, iso_path)

        # Run once with installer from ISO
        self.attach_iso(iso_path)
        self.start_vm()
        self.wait_for_state(self.POWEROFF, timeout=3600)
        self.detach_iso()

        # Run once again to execute port install script.
        self.start_vm()
        self.wait_for_state(self.POWEROFF, timeout=3600)

    def run_cmd(self, cmd, **kwargs):
        if isinstance(cmd, str):
            cmd_str = cmd
        else:
            cmd_str = ' '.join(cmd)

        print(cmd_str)

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        out = proc.stdout.read()
        proc.wait()

        if proc.returncode != 0:
            print(out)
            raise RuntimeError(
                "Command '%s' failed with rc=%d" % (cmd_str, proc.returncode))

    def unpack_iso(self, path):
        iso_dir = os.path.join(self.vm_dir, 'tmpiso')
        if os.path.isdir(iso_dir):
            shutil.rmtree(iso_dir)
        self.run_cmd(['7z', 'x', path, '-o' + iso_dir])

        shutil.rmtree(os.path.join(iso_dir, '[BOOT]'))

        self.run_cmd(
            ['gzip', '-d', 'initrd.gz'],
            cwd=iso_dir)
        return iso_dir

    def generate_iso(self, iso_dir, path):
        self.run_cmd(
            ['gzip', 'initrd'],
            cwd=iso_dir)

        self.run_cmd(
            ['mkisofs',
             '-r',
             '-V', 'ubuntu 16.04 netboot unattended',
             '-cache-inodes', '-J', '-l',
             '-b', 'isolinux.bin',
             '-c', 'boot.cat',
             '-no-emul-boot',
             '-boot-load-size', '4',
             '-boot-info-table',
             '-input-charset', 'utf-8',
             '-o', os.path.join(path + '.partial'),
             './'],
            cwd=iso_dir,
        )

        os.rename(path + '.partial', path)

    def get_xkb_layout(self):
        return subprocess.check_output(
            '. /etc/default/keyboard && echo $XKBLAYOUT',
            shell=True).decode('ascii').strip()

    def get_timezone(self):
        with open('/etc/timezone', 'r') as fp:
            return fp.readline().strip()

    def create_preseed_cfg(self, iso_dir):
        preseed = PRESEED_TEMPLATE.format(
            hostname='noisicaa-test',
            username='testuser',
            password='123',
            keyboard_layout=self.get_xkb_layout(),
            timezone=self.get_timezone(),
        )

        with open(os.path.join(iso_dir, 'preseed.cfg'), 'w') as fp:
            fp.write(preseed)

        # Add to initrd.
        self.run_cmd(
            'echo "./preseed.cfg" | fakeroot cpio -o -H newc -A -F "./initrd"',
            shell=True,
            cwd=iso_dir)

        with open(os.path.join(iso_dir, 'rc.local'), 'w') as fp:
            fp.write(RC_LOCAL_SCRIPT)
        os.chmod(os.path.join(iso_dir, 'rc.local'), 0o775)

        # Add to initrd.
        self.run_cmd(
            'echo "./rc.local" | fakeroot cpio -o -H newc -A -F "./initrd"',
            shell=True,
            cwd=iso_dir)

    def patch_grub_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'boot', 'grub', 'grub.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('menuentry "Install"'):
                        fpout.write(r'''menuentry "Unattended Install" {
	set gfxpayload=keep
	linux	/linux auto=true priority=critical preseed/file=/preseed.cfg --- quiet
	initrd	/initrd.gz
}

''')
                    fpout.write(line)

        os.rename(path + '.new', path)

    def patch_isolinux_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'isolinux.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('timeout '):
                        fpout.write('timeout 100\n')
                        continue
                    fpout.write(line)

        os.rename(path + '.new', path)

    def patch_txt_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'txt.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('default install'):
                        fpout.write(r'''default unattended
label unattended
	menu label ^Unattended Install
	menu default
	kernel linux
	append vga=788 initrd=initrd.gz auto=true priority=critical preseed/file=/preseed.cfg --- quiet
''')
                        continue

                    if line.strip().startswith('menu default'):
                        continue
                    fpout.write(line)

        os.rename(path + '.new', path)

    def patch_iso(self, orig_iso_path, patched_iso_path):
        iso_dir = self.unpack_iso(orig_iso_path)

        self.create_preseed_cfg(iso_dir)
        self.patch_grub_cfg(iso_dir)
        self.patch_isolinux_cfg(iso_dir)
        self.patch_txt_cfg(iso_dir)

        self.generate_iso(iso_dir, patched_iso_path)

    def do_test(self, settings):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        client.connect(self.get_ip(timeout=600), username='testuser', password='123')

        with client.open_sftp() as sftp:
            with sftp.open('runtest.sh', 'w') as fp:
                fp.write(TEST_SCRIPT.format(settings=settings))
            sftp.chmod('runtest.sh', 0o775)

            with sftp.open('wrap.sh', 'w') as fp:
                fp.write(WRAP_SCRIPT)
            sftp.chmod('wrap.sh', 0o775)

            if settings.source == 'local':
                self.run_cmd(['git', 'config', 'core.quotepath', 'off'])
                proc = subprocess.Popen(
                    ['bash', '-c', 'tar -c -z -T<(git ls-tree --full-tree -r --name-only HEAD) -f-'],
                    cwd=vm.ROOT_DIR,
                    stdout=subprocess.PIPE)
                with sftp.open('local.tar.gz', 'wb') as fp:
                    while True:
                        buf = proc.stdout.read(1024)
                        if not buf:
                            break
                        fp.write(buf)
                proc.wait()
                assert proc.returncode == 0

        print("%s: Running test..." % self.name)

        _, stdout, _ = client.exec_command('./wrap.sh')
        out = stdout.read().strip()
        if out == b'SUCCESS':
            print('  OK')
            return True
        else:
            print('  FAILED')
            with client.open_sftp() as sftp:
                with sftp.open('test.log', 'rb') as fp:
                    log = fp.read()
            sys.stdout.buffer.write(log)
            return False
