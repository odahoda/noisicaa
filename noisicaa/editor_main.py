#!/usr/bin/python3

import argparse
import asyncio
import subprocess
import sys
import time
import signal

from .constants import EXIT_SUCCESS, EXIT_RESTART, EXIT_RESTART_CLEAN
from .runtime_settings import RuntimeSettings
from . import logging
from .core import process_manager

logger = logging.getLogger(__name__)


async def main_async(event_loop, runtime_settings, paths):
    manager = process_manager.ProcessManager(event_loop)
    async with manager:
        while True:
            proc = await manager.start_process(
                'ui', 'noisicaa.ui.ui_process.UIProcess',
                runtime_settings=runtime_settings, paths=paths)
            await proc.wait()

            if proc.returncode == EXIT_RESTART:
                runtime_settings.start_clean = False

            elif proc.returncode == EXIT_RESTART_CLEAN:
                runtime_settings.start_clean = True

            elif (proc.returncode != EXIT_SUCCESS
                  and runtime_settings.dev_mode):
                runtime_settings.start_clean = False

                delay = next_retry - time.time()
                if delay > 0:
                    logger.warn(
                        "Sleeping %.1fsec before restarting.", delay)
                    await asyncio.sleep(delay)

            else:
                return proc.returncode


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

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(
            main_async(event_loop, runtime_settings, args.path))
    finally:
        event_loop.stop()
        event_loop.close()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
