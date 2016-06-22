#!/usr/bin/python3

import argparse
import asyncio
import subprocess
import sys
import time
import signal

import pyximport
pyximport.install()

from .constants import EXIT_SUCCESS, EXIT_RESTART, EXIT_RESTART_CLEAN
from .runtime_settings import RuntimeSettings
from . import logging
from .core import process_manager
from .ui import ui_process

async def main_async(event_loop, runtime_settings, args):
    manager = process_manager.ProcessManager(event_loop)
    async with manager:
        proc = await manager.start_process('ui', ui_process.UIProcess)
        await proc.wait()


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

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(
            main_async(event_loop, runtime_settings, args))
    finally:
        event_loop.stop()
        event_loop.close()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
