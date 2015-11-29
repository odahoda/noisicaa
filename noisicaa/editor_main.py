#!/usr/bin/python3

import argparse
import subprocess
import sys
import time
import signal

from .constants import EXIT_SUCCESS, EXIT_RESTART, EXIT_RESTART_CLEAN
from .runtime_settings import RuntimeSettings
from . import logging

SIGNAL_NAME = dict(
    (getattr(signal, n), n)
    for n in dir(signal)
    if n.startswith('SIG') and '_' not in n)


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

    logger = logging.getLogger('ui.editor_main')

    assert sys.executable is not None
    while True:
        next_retry = time.time() + 5

        cmd = [sys.executable,
               '-m', 'noisicaa.editor']
        cmd += runtime_settings.as_args()
        cmd += args.path
        logger.info("Starting editor in subprocess: %s", ' '.join(cmd))
        proc = subprocess.Popen(cmd, bufsize=1, stderr=subprocess.PIPE)
        try:
            empty_lines = []
            while True:
                l = proc.stderr.readline()
                if not l:
                    break
                if len(l.rstrip(b'\r\n')) == 0:
                    # Buffer empty lines, so we can discard those that are followed
                    # by a message that we also want to discard.
                    empty_lines.append(l)
                    continue
                if b'fluid_synth_sfont_unref' in l:
                    # Discard annoying error message from libfluidsynth. It is also
                    # preceeded by a empty line, which we also throw away.
                    empty_lines.clear()
                    continue
                while len(empty_lines) > 0:
                    sys.stderr.buffer.write(empty_lines.pop(0))
                sys.stderr.buffer.write(l)
                sys.stderr.flush()

            while len(empty_lines) > 0:
                sys.stderr.buffer.write(empty_lines.pop(0))

            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()

        rc = proc.returncode
        if rc < 0:
            sig = -rc
            logger.error("Subprocess terminated by signal %s", SIGNAL_NAME[sig])
            if sig == signal.SIGTERM and runtime_settings.dev_mode:
                rc = EXIT_SUCCESS
        elif rc > 0:
            logger.error("Subprocess finished with returncode %d", rc)
        else:
            logger.info("Subprocess finished with returncode %d", rc)

        if rc == EXIT_SUCCESS:
            return EXIT_SUCCESS

        if rc == EXIT_RESTART:
            runtime_settings.start_clean = False

        elif rc == EXIT_RESTART_CLEAN:
            runtime_settings.start_clean = True

        elif runtime_settings.dev_mode:
            runtime_settings.start_clean = False

            delay = next_retry - time.time()
            if delay > 0:
                logger.warn("Sleeping %.1fsec before restarting.", delay)
                time.sleep(delay)

        else:
            return proc.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv))
