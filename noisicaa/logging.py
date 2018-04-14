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

import sys
import logging.handlers
from logging import *  # pylint: disable=W0614,W0401
import queue
from typing import Any, Dict, Optional, List, Tuple, Type  # pylint: disable=unused-import

from . import runtime_settings as runtime_settings_lib


class WrappingFormatter(Formatter):
    def formatMessage(self, record: LogRecord) -> str:
        record.message = record.message.replace('\n', '\n\t')
        # Typeshed doesn't know about formatMessage. It is also not documented, so it might
        # not be the best idea to extend it...
        return super().formatMessage(record)  # type: ignore


class LogFilter(Filter):
    def __init__(self, level_spec: str) -> None:
        super().__init__()

        self.levels = []  # type: List[Tuple[str, int]]

        for pair in level_spec.split(','):
            if '=' in pair:
                logger_name, level_name = pair.split('=')
            else:
                logger_name = ''
                level_name = pair
            log_level = {
                'debug': DEBUG,
                'info': INFO,
                'warning': WARNING,
                'error': ERROR,
                'critical': CRITICAL,
            }[level_name]
            self.levels.append((logger_name, log_level))

    def filter(self, record: LogRecord) -> bool:
        for logger_name, level in self.levels:
            if (record.levelno >= level and (logger_name == ''
                                             or record.name == logger_name
                                             or record.name.startswith(logger_name + '.'))):
                return True
        return False


class HandlerGroup(Handler):
    def __init__(self) -> None:
        super().__init__()
        self.__handlers = {}  # type: Dict[str, Handler]

    def emit(self, record: LogRecord) -> None:
        raise RuntimeError

    def handle(self, record: LogRecord) -> None:
        with self.lock:
            for handler in self.__handlers.values():
                handler.handle(record)

    def add_handler(self, name: str, handler: Handler) -> None:
        with self.lock:
            assert name not in self.__handlers
            self.__handlers[name] = handler

    def remove_handler(self, name: str) -> Optional[Handler]:
        with self.lock:
            return self.__handlers.pop(name, None)


class LogManager(object):
    def __init__(self, runtime_settings: runtime_settings_lib.RuntimeSettings) -> None:
        self.runtime_settings = runtime_settings

        self.root_logger = None  # type: Logger
        self.queue = None  # type: queue.Queue
        self.queue_handler = None  # type: logging.handlers.QueueHandler
        self.queue_listener = None  # type: logging.handlers.QueueListener
        self.handlers = None  # type: HandlerGroup

    def __enter__(self) -> 'LogManager':
        self.setup()
        return self

    def __exit__(self, *args: Any) -> bool:
        self.cleanup()
        return False

    def setup(self) -> None:
        captureWarnings(True)

        # Remove all existing log handlers and install a single QueueHandler.
        self.root_logger = getLogger()
        for handler in self.root_logger.handlers:
            self.root_logger.removeHandler(handler)
        self.root_logger.setLevel(DEBUG)

        self.queue = queue.Queue()
        self.queue_handler = logging.handlers.QueueHandler(self.queue)
        self.root_logger.addHandler(self.queue_handler)

        # Make loggers of 3rd party modules less noisy.
        for other in ('quamash', 'vext'):
            getLogger(other).setLevel(WARNING)

        # Create a QueueListener that reads from the queue and sends log
        # records to the actual log handlers.
        self.handlers = HandlerGroup()

        self.handlers.add_handler('stderr', self.create_stderr_logger())

        if self.runtime_settings.log_file:
            self.handlers.add_handler('file', self.create_file_logger())

        self.queue_listener = logging.handlers.QueueListener(
            self.queue, self.handlers, respect_handler_level=True)
        self.queue_listener.start()

    def cleanup(self) -> None:
        if self.queue_handler is not None:
            self.root_logger.removeHandler(self.queue_handler)
            self.queue_handler = None

        if self.queue_listener is not None:
            self.queue_listener.stop()
            self.queue_listener = None

        self.handlers = None

        if self.queue is not None:
            assert self.queue.empty()
            self.queue = None

    def add_handler(self, name: str, handler: Handler) -> None:
        self.handlers.add_handler(name, handler)

    def remove_handler(self, name: str) -> Optional[Handler]:
        return self.handlers.remove_handler(name)

    def create_stderr_logger(self) -> Handler:
        handler = StreamHandler(sys.stderr)
        handler.addFilter(LogFilter(self.runtime_settings.log_level))
        handler.setFormatter(
            WrappingFormatter(
                '%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s'))
        return handler

    def create_file_logger(self) -> Handler:
        handler = logging.handlers.RotatingFileHandler(
            self.runtime_settings.log_file,
            maxBytes=100 * 2**20,
            backupCount=9,
            encoding='utf-8')
        handler.setLevel(DEBUG)
        handler.setFormatter(WrappingFormatter(
            '%(asctime)s\t%(levelname)s\t%(process)s\t%(thread)08x\t%(name)s\t%(message)s',
            '%Y%m%d-%H%M%S'))
        return handler
