#!/usr/bin/python3

import collections
import logging
import io
import os
import os.path
import select
import shutil
import subprocess
import sys
import textwrap

import paramiko
import Xlib.support.connect as xlib_connect

from . import vm

logger = logging.getLogger(__name__)


class PreseedCfg(object):
    def __init__(self):
        self.__data = collections.OrderedDict()

    def __str__(self):
        b = io.StringIO()
        self.dump(b)
        return b.getvalue()

    def insert(self, target, var, value_type, value):
        assert value_type in ('string', 'boolean', 'select', 'multiselect', 'note', 'text', 'password')
        self.__data[(target, var)] = (value_type, value)

    def dump(self, fp):
        for (target, var), (value_type, value) in self.__data.items():
            fp.write('%s %s %s' % (target, var, value_type))
            if value is not None:
                for idx, line in enumerate(value.splitlines(False)):
                    if idx == 0:
                        fp.write(' %s' % line)
                    else:
                        fp.write(' \\\n  %s' % line)
            fp.write('\n')


class DebianLike(vm.VM):
    def __init__(self, *, iso_url, iso_name, **kwargs):
        super().__init__(**kwargs)

        self.__iso_url = iso_url
        self.__iso_name = iso_name

    async def do_install(self):
        orig_iso_path = os.path.join(self.cache_dir, self.__iso_name)
        iso_path = os.path.join(self.vm_dir, 'installer.iso')

        if not os.path.isfile(orig_iso_path):
            await self.download_file(self.__iso_url, orig_iso_path)

        if not os.path.isfile(iso_path):
            self.patch_iso(orig_iso_path, iso_path)

        # Run once with installer from ISO
        await self.attach_iso(iso_path)
        await self.start()
        await self.wait_for_state(self.POWEROFF, timeout=3600)
        await self.detach_iso()

    def build_preseed(self):
        cfg = PreseedCfg()

        ### Localization
        cfg.insert('d-i', 'debian-installer/locale', 'string', 'en_US.UTF-8')
        cfg.insert('d-i', 'localechooser/supported-locales', 'multiselect', 'en_US.UTF-8, de_DE.UTF-8')
        cfg.insert('d-i', 'console-setup/ask_detect', 'boolean', 'false')
        cfg.insert('d-i', 'keyboard-configuration/xkb-keymap', 'select', self.__get_xkb_layout())

        ### Network configuration
        cfg.insert('d-i', 'netcfg/choose_interface', 'select', 'auto')
        cfg.insert('d-i', 'netcfg/hostname', 'string', self.hostname)
        cfg.insert('d-i', 'netcfg/get_hostname', 'string', self.hostname)
        cfg.insert('d-i', 'netcfg/get_domain', 'string', 'unnamed')
        cfg.insert('d-i', 'hw-detect/load_firmware', 'boolean', 'true')
        cfg.insert('d-i', 'netcfg/wireless_wep', 'string', None)

        ### Account setup
        cfg.insert('d-i', 'passwd/root-login', 'boolean', 'false')
        cfg.insert('d-i', 'passwd/make-user', 'boolean', 'true')
        cfg.insert('d-i', 'passwd/user-fullname', 'string', 'Tester')
        cfg.insert('d-i', 'passwd/username', 'string', 'testuser')
        cfg.insert('d-i', 'passwd/user-password', 'password', '123')
        cfg.insert('d-i', 'passwd/user-password-again', 'password', '123')

        ### Clock and time zone setup
        cfg.insert('d-i', 'clock-setup/utc', 'boolean', 'true')
        cfg.insert('d-i', 'time/zone', 'string', self.__get_timezone())
        cfg.insert('d-i', 'clock-setup/ntp', 'boolean', 'true')

        ### Base system installation
        cfg.insert('d-i', 'base-installer/install-recommends', 'boolean', 'true')

        ### Package selection
        cfg.insert('tasksel', 'tasksel/first', 'multiselect', 'none')
        cfg.insert('d-i', 'pkgsel/include', 'string', 'openssh-server')
        cfg.insert('d-i', 'pkgsel/upgrade', 'select', 'full-upgrade')

        ### Preseeding other packages
        cfg.insert('d-i', 'preseed/late_command', 'string', textwrap.dedent('''\
            /bin/echo >/target/etc/sudoers.d/testuser "testuser ALL=(ALL) NOPASSWD:ALL"
        '''))

        ### Boot loader installation
        cfg.insert('d-i', 'grub-installer/only_debian', 'boolean', 'true')
        cfg.insert('d-i', 'grub-installer/with_other_os', 'boolean', 'true')
        cfg.insert('d-i', 'grub-installer/bootdev ', 'string', '/dev/sda')

        ### Finishing up the installation
        cfg.insert('d-i', 'cdrom-detect/eject', 'boolean', 'true')
        cfg.insert('d-i', 'finish-install/reboot_in_progress', 'note', None)
        cfg.insert('d-i', 'debian-installer/exit/poweroff', 'boolean', 'true')

        return cfg

    def __get_xkb_layout(self):
        return subprocess.check_output(
            '. /etc/default/keyboard && echo $XKBLAYOUT',
            shell=True).decode('ascii').strip()

    def __get_timezone(self):
        with open('/etc/timezone', 'r') as fp:
            return fp.readline().strip()

    def patch_iso(self, orig_iso_path, patched_iso_path):
        raise NotImplementedError

    def _run_cmd(self, cmd, **kwargs):
        if isinstance(cmd, str):
            cmd_str = cmd
        else:
            cmd_str = ' '.join(cmd)

        logger.info(cmd_str)

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        out = proc.stdout.read()
        proc.wait()

        if proc.returncode != 0:
            logger.info(out)
            raise RuntimeError(
                "Command '%s' failed with rc=%d" % (cmd_str, proc.returncode))


class Debian(DebianLike):
    def build_preseed(self):
        cfg = super().build_preseed()

        ### Mirror settings
        cfg.insert('d-i', 'mirror/country', 'string', 'manual')
        cfg.insert('d-i', 'mirror/http/hostname', 'string', 'http.us.debian.org')
        cfg.insert('d-i', 'mirror/http/directory', 'string', '/debian')
        cfg.insert('d-i', 'mirror/http/proxy', 'string', None)

        ### Partitioning
        ## Partitioning example
        # If the system has free space you can choose to only partition that space.
        # This is only honoured if partman-auto/method (below) is not set.
        #d-i partman-auto/init_automatically_partition select biggest_free

        # Alternatively, you may specify a disk to partition. If the system has only
        # one disk the installer will default to using that, but otherwise the device
        # name must be given in traditional, non-devfs format (so e.g. /dev/sda
        # and not e.g. /dev/discs/disc0/disc).
        # For example, to use the first SCSI/SATA hard disk:
        #d-i partman-auto/disk string /dev/sda
        # In addition, you'll need to specify the method to use.
        # The presently available methods are:
        # - regular: use the usual partition types for your architecture
        # - lvm:     use LVM to partition the disk
        # - crypto:  use LVM within an encrypted partition
        cfg.insert('d-i', 'partman-auto/method', 'string', 'regular')

        cfg.insert('d-i', 'partman-lvm/device_remove_lvm', 'boolean', 'true')
        cfg.insert('d-i', 'partman-md/device_remove_md', 'boolean', 'true')
        cfg.insert('d-i', 'partman-lvm/confirm', 'boolean', 'true')
        cfg.insert('d-i', 'partman-lvm/confirm_nooverwrite', 'boolean', 'true')
        cfg.insert('d-i', 'partman-auto/choose_recipe', 'select', 'atomic')
        cfg.insert('d-i', 'partman-partitioning/confirm_write_new_label', 'boolean', 'true')
        cfg.insert('d-i', 'partman/choose_partition', 'select', 'finish')
        cfg.insert('d-i', 'partman/confirm', 'boolean', 'true')
        cfg.insert('d-i', 'partman/confirm_nooverwrite', 'boolean', 'true')

        ### Apt setup
        cfg.insert('d-i', 'apt-setup/non-free', 'boolean', 'true')
        cfg.insert('d-i', 'apt-setup/contrib', 'boolean', 'true')
        #d-i apt-setup/use_mirror boolean false
        cfg.insert('d-i', 'apt-setup/services-select', 'multiselect', 'security, updates')
        cfg.insert('d-i', 'apt-setup/security_host', 'string', 'security.debian.org')
        cfg.insert('apt-cdrom-setup', 'apt-setup/cdrom/set-first', 'boolean', 'false')

        ### Package selection
        cfg.insert('popularity-contest', 'popularity-contest/participate', 'boolean', 'false')

        ### Boot loader installation
        cfg.insert('d-i', 'grub-installer/only_debian', 'boolean', 'true')
        cfg.insert('d-i', 'grub-installer/with_other_os', 'boolean', 'true')
        cfg.insert('d-i', 'grub-installer/bootdev ', 'string', '/dev/sda')

        ### Preseeding other packages
        cfg.insert('d-i', 'preseed/late_command', 'string', textwrap.dedent('''\
            /bin/echo >/target/etc/sudoers.d/testuser "testuser ALL=(ALL) NOPASSWD:ALL"
            adduser testuser audio
        '''))

        return cfg

    def __unpack_iso(self, path):
        iso_dir = os.path.join(self.vm_dir, 'tmpiso')
        if os.path.isdir(iso_dir):
            shutil.rmtree(iso_dir)
        self._run_cmd(['7z', 'x', path, '-o' + iso_dir])

        shutil.rmtree(os.path.join(iso_dir, '[BOOT]'))

        self._run_cmd(
            ['gzip', '-d', 'install.amd/initrd.gz'],
            cwd=iso_dir)
        return iso_dir

    def __generate_iso(self, iso_dir, path):
        self._run_cmd(
            ['gzip', 'install.amd/initrd'],
            cwd=iso_dir)

        self._run_cmd(
            ['mkisofs',
             '-r',
             '-V', 'Debian testvm',
             '-cache-inodes', '-J', '-l',
             '-b', 'isolinux/isolinux.bin',
             '-c', 'isolinux/boot.cat',
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
            'echo "./preseed.cfg" | fakeroot cpio -o -H newc -A -F "./install.amd/initrd"',
            shell=True,
            cwd=iso_dir)

    def __patch_grub_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'boot', 'grub', 'grub.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('menuentry '):
                        fpout.write(r'''menuentry "Unattended Install" {
	set background_color=black
	linux	/install.amd/vmlinuz vga=788 preseed/file=/preseed.cfg --- quiet
	initrd	/install.amd/initrd.gz
}

''')
                    fpout.write(line)

        os.rename(path + '.new', path)

    def __patch_isolinux_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'isolinux', 'isolinux.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('timeout '):
                        fpout.write('timeout 30\n')
                        continue
                    fpout.write(line)

        os.rename(path + '.new', path)

    def __patch_menu_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'isolinux/menu.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('include stdmenu.cfg'):
                        fpout.write(r'''default unattended
label unattended
	menu label ^Unattended Install
	menu default
	kernel /install.amd/vmlinuz
	append vga=788 initrd=/install.amd/initrd.gz preseed/file=/preseed.cfg --- quiet
''')
                        continue

                    fpout.write(line)

        os.rename(path + '.new', path)

    def __patch_gtk_cfg(self, iso_dir):
        path = os.path.join(iso_dir, 'isolinux/gtk.cfg')
        with open(path, 'r') as fpin:
            with open(path + '.new', 'w') as fpout:
                for line in fpin:
                    if line.startswith('default installgui'):
                        continue

                    if line.strip().startswith('menu default'):
                        continue
                    fpout.write(line)

        os.rename(path + '.new', path)

    def patch_iso(self, orig_iso_path, patched_iso_path):
        iso_dir = self.__unpack_iso(orig_iso_path)
        try:
            self.__create_preseed_cfg(iso_dir)
            self.__patch_grub_cfg(iso_dir)
            self.__patch_isolinux_cfg(iso_dir)
            self.__patch_menu_cfg(iso_dir)
            self.__patch_gtk_cfg(iso_dir)
            self.__generate_iso(iso_dir, patched_iso_path)
        finally:
            shutil.rmtree(iso_dir)


class Debian9(Debian):
    def __init__(self, **kwargs):
        super().__init__(
            iso_url='https://cdimage.debian.org/cdimage/archive/9.9.0/amd64/iso-cd/debian-9.9.0-amd64-netinst.iso',
            iso_name='debian-9.9.0-amd64-netinst.iso',
            **kwargs,
        )
