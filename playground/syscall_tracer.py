#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

import logging
import os
import signal
import traceback
import time

from ptrace.binding import func as ptrace
from ptrace import syscall

logger = logging.getLogger(__name__)


class SyscallTracer(object):
    def __init__(self, thread, tid):
        self.__thread = thread
        self.__tid = tid

    def setup(self):
        logger.info("Setting up syscall tracer for thread %x (tid=%d)...", self.__thread.ident, self.__tid)
        main_pid = os.fork()
        if main_pid < 0:
            raise OSError("fork failed")
        if main_pid == 0:
            for _ in range(10):
                open('/proc/1/status', 'rb').read()
                time.sleep(0.5)
            os._exit(0)
        else:
            self.__tracer_main(main_pid)
            logger.info("tracer pid=%d", main_pid)

    def cleanup(self):
        logger.info("Cleaning up syscall tracer for thread %d (tid=%d)...", self.__thread.ident, self.__tid)

    def __tracer_main(self, tid):
        signal.signal(signal.SIGTRAP, signal.SIG_IGN)

        ptrace.ptrace_attach(tid)

        current_syscall = None

        while True:
            _, status = os.waitpid(tid, 0)

            if os.WIFEXITED(status):
                logger.info("Thread exited with status %d", os.WEXITSTATUS(status))
                break

            if os.WIFCONTINUED(status):
                logger.info("Thread woke up")

            elif os.WIFSTOPPED(status):
                signum = os.WSTOPSIG(status)
                is_syscall = bool(signum & 0x80)
                signum &= 0x7f

                forward_signum = 0
                sig = signal.Signals(signum)
                logger.debug("Thread stopped with signal %s", sig)
                if sig == signal.SIGSTOP:
                    logger.info("Setting up trace options...")
                    ptrace.ptrace_setoptions(tid, ptrace.PTRACE_O_TRACESYSGOOD)

                elif sig == signal.SIGTRAP and is_syscall:
                    regs = ptrace.ptrace_getregs(tid)
                    if current_syscall is None:
                        current_syscall = getattr(regs, syscall.SYSCALL_REGISTER)

                    else:
                        return_value = getattr(regs, syscall.RETURN_VALUE_REGISTER)
                        syscall_name = syscall.SYSCALL_NAMES.get(
                            current_syscall, 'unknown<%d>' % current_syscall)
                        logger.info("syscall(%s) = %d", syscall_name, return_value)
                        current_syscall = None

                else:
                    forward_signum = signum

                ptrace.ptrace_syscall(tid, forward_signum)

            elif os.WIFSIGNALED(status):
                signum = os.WTERMSIG(status)
                sig = signal.Signals(signum)
                logger.info("Thread received signal %s", sig)
                ptrace.ptrace_syscall(tid, signum)

            else:
                logger.warning("Unknown thread status %d", status)
