#!/usr/bin/python3

import pyximport
pyximport.install()

import argparse
import asyncio
import os
import sys

import quamash

from . import logging
from .runtime_settings import RuntimeSettings
from .ui import ui_process
from .core import ipc

class ProcessImpl(object):
    async def setup(self):
        pass

    async def cleanup(self):
        pass

    def main(self, *args, **kwargs):
        # Create a new event loop to replace the one we inherited.
        self.event_loop = self.create_event_loop()
        asyncio.set_event_loop(self.event_loop)

        try:
            self.event_loop.run_until_complete(
                self.main_async(*args, **kwargs))
        finally:
            pass
            #self.event_loop.stop()
            #self.event_loop.close()

    async def main_async(self, *args, **kwargs):
        self.server = ipc.Server(self.event_loop, 'ui')
        async with self.server:
            try:
                await self.setup()

                return await self.run(*args, **kwargs)
            finally:
                await self.cleanup()


class UIProcess(ui_process.UIProcessMixin, ProcessImpl):
    pass


def main(argv):
    runtime_settings = RuntimeSettings()

    parser = argparse.ArgumentParser(
        prog=argv[0])
    parser.add_argument(
        'path',
        nargs='*',
        help="Project file to open.")
    runtime_settings.init_argparser(parser)
    args = parser.parse_args(args=argv[1:])
    runtime_settings.set_from_args(args)

    logging.init(runtime_settings)

    if runtime_settings.dev_mode:
        import pyximport
        pyximport.install()

    logging.info("RuntimeSettings: %s", runtime_settings.to_json())

    proc = UIProcess()
    proc.main()

    return 0

if __name__ == '__main__':
    # Doing a regular sys.exit() often causes SIGSEGVs somewhere in the PyQT5
    # shutdown code. Let's do a hard exit instead.
    os._exit(main(sys.argv))
