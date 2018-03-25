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

# mypy: loose

import asyncio
import asyncio.streams
import logging
import pprint
import subprocess
import sys
import textwrap

from noisicaa.music import project

logger = logging.getLogger(__name__)


class ProjectDebugger(object):
    def __init__(self, runtime_settings, paths):
        self.runtime_settings = runtime_settings
        self.paths = paths

        self.event_loop = None
        self.stdin = None
        self.stdout = None
        self.project = None

    def run(self):
        self.write("noisicaä project debugger\n\n")

        if len(self.paths) != 1:
            raise ValueError("Exactly one project path must be given.")

        self.event_loop = asyncio.get_event_loop()
        try:
            self.event_loop.run_until_complete(self.run_async(self.paths[0]))
        finally:
            self.event_loop.stop()
            self.event_loop.close()

    def write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    async def readline(self):
        text = await self.event_loop.run_in_executor(None, sys.stdin.readline)
        if text == '':
            raise EOFError
        text = text.rstrip('\n')
        return text

    async def run_async(self, path):
        self.project = project.Project(node_db=None)
        try:
            self.project.open(path)

            self.write("Project '%s' successfully opened.\n" % path)

            while True:
                self.write(">>> ")
                try:
                    inp = await self.readline()
                except EOFError:
                    break

                if inp == '':
                    continue

                elif inp.lower() in ('?', 'help'):
                    self.write(textwrap.dedent("""\
                        Usage:
                          help, ?: Show this text.
                          undo:    Undo latest command in project.
                          dump:    Dump serialized project state.
                          quit:    Exit debugger.
                        """))
                    continue

                elif inp.lower() == 'quit':
                    break

                elif inp.lower() == 'undo':
                    self.project.undo()

                elif inp.lower() == 'dump':
                    subprocess.run(
                        ['/usr/bin/less'],
                        input=pprint.pformat(self.project.serialize()).encode('utf-8'))

                else:
                    self.write(
                        "Unknown command '%s'. Type 'help' to list available commands.\n" % inp)

        except KeyboardInterrupt:
            pass

        finally:
            self.write("Bye.\n")
            self.project.close()
