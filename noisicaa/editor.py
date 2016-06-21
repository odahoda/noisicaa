#!/usr/bin/python3

import argparse
import asyncio
import os
import sys

import quamash

from . import logging
from .runtime_settings import RuntimeSettings

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

    from .ui.editor_app import EditorApp
    app = EditorApp(runtime_settings, args.path)
    event_loop = quamash.QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    with event_loop:
        app.setup()
        try:
            event_loop.run_forever()
        finally:
            app.cleanup()

    return 0

if __name__ == '__main__':
    # Doing a regular sys.exit() often causes SIGSEGVs somewhere in the PyQT5
    # shutdown code. Let's do a hard exit instead.
    os._exit(main(sys.argv))
