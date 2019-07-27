#!/usr/bin/python3

import logging
import os
import os.path
import select
import shutil
import subprocess
import sys
import textwrap

import paramiko
import Xlib.support.connect as xlib_connect

from . import debian

logger = logging.getLogger(__name__)


class Ubuntu(debian.DebianLike):
    def build_preseed(self):
        cfg = super().build_preseed()

        ### Mirror settings
        cfg.insert('d-i', 'mirror/country', 'string', 'manual')
        cfg.insert('d-i', 'mirror/http/hostname', 'string', 'archive.ubuntu.com')
        cfg.insert('d-i', 'mirror/http/directory', 'string', '/ubuntu')
        cfg.insert('d-i', 'mirror/http/proxy', 'string', None)

        ### Account setup
        cfg.insert('d-i', 'user-setup/allow-password-weak', 'boolean', 'true')
        cfg.insert('d-i', 'user-setup/encrypt-home', 'boolean', 'false')

        ### Clock and time zone setup
        cfg.insert('d-i', 'clock-setup/ntp-server', 'string', 'ntp.ubuntu.com')

        ### Partitioning
        cfg.insert('d-i', 'preseed/early_command', 'string', 'umount /media || true')
        cfg.insert('d-i', 'partman-auto/method', 'string', 'lvm')
        cfg.insert('d-i', 'partman-auto-lvm/guided_size', 'string', 'max')
        cfg.insert('d-i', 'partman-lvm/device_remove_lvm', 'boolean', 'true')
        cfg.insert('d-i', 'partman-lvm/confirm', 'boolean', 'true')
        cfg.insert('d-i', 'partman-lvm/confirm_nooverwrite', 'boolean', 'true')
        cfg.insert('d-i', 'partman-auto-lvm/new_vg_name', 'string', 'main')
        cfg.insert('d-i', 'partman-md/device_remove_md', 'boolean', 'true')
        cfg.insert('d-i', 'partman-md/confirm', 'boolean', 'true')
        cfg.insert('d-i', 'partman-partitioning/confirm_write_new_label', 'boolean', 'true')
        cfg.insert('d-i', 'partman/choose_partition', 'select', 'finish')
        cfg.insert('d-i', 'partman/confirm', 'boolean', 'true')
        cfg.insert('d-i', 'partman/confirm_nooverwrite', 'boolean', 'true')
        cfg.insert('d-i', 'partman-basicmethods/method_only', 'boolean', 'false')

        ### Disk layout
        cfg.insert('d-i', 'partman-auto/expert_recipe', 'string', textwrap.dedent('''\
          boot-root ::
            512 512 512 ext4
              $primary{ }
              $bootable{ }
              method{ format } format{ }
              use_filesystem{ } filesystem{ ext4 }
              mountpoint{ /boot }
            .
            1024 102400000 1000000000 ext4
              $lvmok{ }
              method{ format } format{ }
              use_filesystem{ } filesystem{ ext4 }
              mountpoint{ / }
              lv_name{ root }
            .
            200% 200% 200% linux-swap
              $lvmok{ }
              method{ swap } format{ }
              lv_name{ swap }
            .
        '''))

        ### Base system installation
        cfg.insert('d-i', 'base-installer/kernel/image', 'string', 'linux-generic')

        ### Apt setup
        cfg.insert('d-i', 'apt-setup/restricted', 'boolean', 'true')
        cfg.insert('d-i', 'apt-setup/universe', 'boolean', 'true')
        cfg.insert('d-i', 'apt-setup/backports', 'boolean', 'true')
        cfg.insert('d-i', 'apt-setup/use_mirror', 'boolean', 'false')
        cfg.insert('d-i', 'apt-setup/services-select', 'multiselect', 'security, updates')
        cfg.insert('d-i', 'apt-setup/security_host', 'string', 'security.ubuntu.com')
        cfg.insert('d-i', 'apt-setup/security_path', 'string', '/ubuntu')

        ### Package selection
        cfg.insert('d-i', 'pkgsel/update-policy', 'select', 'none')

        ### Finishing up the installation
        cfg.insert('d-i', 'debian-installer/splash', 'boolean', 'false')

        return cfg

    def __unpack_iso(self, path):
        iso_dir = os.path.join(self.vm_dir, 'tmpiso')
        if os.path.isdir(iso_dir):
            shutil.rmtree(iso_dir)
        self._run_cmd(['7z', 'x', path, '-o' + iso_dir])

        shutil.rmtree(os.path.join(iso_dir, '[BOOT]'))

        self._run_cmd(
            ['gzip', '-d', 'initrd.gz'],
            cwd=iso_dir)
        return iso_dir

    def __generate_iso(self, iso_dir, path):
        self._run_cmd(
            ['gzip', 'initrd'],
            cwd=iso_dir)

        self._run_cmd(
            ['mkisofs',
             '-r',
             '-V', 'Ubuntu netboot unattended',
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

    def __create_preseed_cfg(self, iso_dir):
        cfg = self.build_preseed()
        logger.debug("preseed.cfg:\n%s", cfg)
        with open(os.path.join(iso_dir, 'preseed.cfg'), 'w') as fp:
            cfg.dump(fp)

        # Add to initrd.
        self._run_cmd(
            'echo "./preseed.cfg" | fakeroot cpio -o -H newc -A -F "./initrd"',
            shell=True,
            cwd=iso_dir)

    def __patch_grub_cfg(self, iso_dir):
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

    def __patch_isolinux_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'isolinux.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('timeout '):
                        fpout.write('timeout 100\n')
                        continue
                    fpout.write(line)

        os.rename(path + '.new', path)

    def __patch_txt_cfg(self, iso_dir):
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
        iso_dir = self.__unpack_iso(orig_iso_path)

        self.__create_preseed_cfg(iso_dir)
        self.__patch_grub_cfg(iso_dir)
        self.__patch_isolinux_cfg(iso_dir)
        self.__patch_txt_cfg(iso_dir)

        self.__generate_iso(iso_dir, patched_iso_path)


class Ubuntu_16_04(Ubuntu):
    def __init__(self, **kwargs):
        super().__init__(
            iso_url=('http://archive.ubuntu.com/ubuntu/dists/xenial-updates/main/'
                     'installer-amd64/current/images/netboot/mini.iso'),
            iso_name='ubuntu-xenial-amd64-netboot.iso',
            **kwargs,
        )


class Ubuntu_18_04(Ubuntu):
    def __init__(self, **kwargs):
        super().__init__(
            iso_url=('http://archive.ubuntu.com/ubuntu/dists/bionic-updates/main/'
                     'installer-amd64/current/images/netboot/mini.iso'),
            iso_name='ubuntu-bionic-amd64-netboot.iso',
            **kwargs,
        )

