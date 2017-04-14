#!/usr/bin/python3

import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)


class OpCode(object):
    def __repr__(self):
        return type(self).__name__


class PipelineVMSpec(object):
    def __init__(self):
        self.opcodes = []
        self.buffer_size = 0


class PipelineVM(object):
    def __init__(self):
        self.__vm_thread = None
        self.__vm_started = None
        self.__vm_exit = None
        self.__vm_lock = None

        self.__spec = None
        self.__buffer = None

    def setup(self):
        self.__vm_lock = threading.Lock()
        self.__vm_started = threading.Event()
        self.__vm_exit = threading.Event()
        self.__vm_thread = threading.Thread(target=self.vm_main)
        self.__vm_thread.start()
        self.__vm_started.wait()
        logger.info("VM up and running.")

    def cleanup(self):
        if self.__vm_thread is not None:
            logger.info("Shutting down VM thread...")
            self.__vm_exit.set()
            self.__vm_thread.join()
            self.__vm_thread = None
            logger.info("VM thread stopped.")

        self.__vm_started = None
        self.__vm_exit = None
        self.__vm_lock = None

        self.__spec = None
        self.__buffer = None

    def set_spec(self, spec):
        with self.__vm_lock:
            if self.__spec is not None:
                self.__buffer = None
                self.__spec = None

            if spec is not None:
                self.__buffer = bytearray(spec.buffer_size)
                self.__spec = spec

    def vm_main(self):
        try:
            logger.info("Starting VM...")
            self.__vm_started.set()

            while True:
                if self.__vm_exit.is_set():
                    logger.info("Exiting VM mainloop.")
                    break

                with self.__vm_lock:
                    spec = self.__spec
                    if spec is not None:
                        self.run_vm(spec)

                time.sleep(0.1)

        except:  # pylint: disable=bare-except
            sys.stdout.flush()
            sys.excepthook(*sys.exc_info())
            sys.stderr.flush()
            os._exit(1)  # pylint: disable=protected-access

        finally:
            logger.info("VM finished.")

    def run_vm(self, spec):
        for opcode in spec.opcodes:
            logger.info("Executing opcode %s", opcode)
