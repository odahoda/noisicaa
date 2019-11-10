#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import base64
import importlib
import logging
import os
import pickle
import struct
import sys
import threading
import traceback

from . import stacktrace
from .logging import init_pylogging
from . import process_manager_io

logger = logging.getLogger(__name__)


class ChildLogHandler(logging.Handler):
    def __init__(self, log_fd: int) -> None:
        super().__init__()
        self.__log_fd = log_fd
        self.__lock = threading.Lock()

    def handle(self, record: logging.LogRecord) -> None:
        record_attrs = {
            'msg': record.getMessage(),
            'args': (),
        }
        for attr in (
                'created', 'exc_text', 'filename',
                'funcName', 'levelname', 'levelno', 'lineno',
                'module', 'msecs', 'name', 'pathname', 'process',
                'relativeCreated', 'thread', 'threadName'):
            record_attrs[attr] = record.__dict__[attr]

        serialized_record = pickle.dumps(record_attrs, protocol=pickle.HIGHEST_PROTOCOL)
        msg = bytearray()
        msg += b'RECORD'
        msg += struct.pack('>L', len(serialized_record))
        msg += serialized_record

        with self.__lock:
            while msg:
                written = os.write(self.__log_fd, msg)
                msg = msg[written:]

    def emit(self, record: logging.LogRecord) -> None:
        pass


if __name__ == '__main__':
    try:
        assert len(sys.argv) == 2

        args = pickle.loads(base64.b64decode(sys.argv[1]))

        request_in = args['request_in']
        response_out = args['response_out']
        logger_out = args['logger_out']
        log_level = args['log_level']
        entry = args['entry']
        name = args['name']
        manager_address = args['manager_address']
        tmp_dir = args['tmp_dir']
        kwargs = args['kwargs']

        # Remove all existing log handlers, and install a new
        # handler to pipe all log messages back to the manager
        # process.
        root_logger = logging.getLogger()
        while root_logger.handlers:
            root_logger.removeHandler(root_logger.handlers[0])
        root_logger.addHandler(ChildLogHandler(logger_out))
        root_logger.setLevel(log_level)

        # Make loggers of 3rd party modules less noisy.
        for other in ['quamash']:
            logging.getLogger(other).setLevel(logging.WARNING)

        stacktrace.init()
        init_pylogging()

        mod_name, cls_name = entry.rsplit('.', 1)
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        impl = cls(
            name=name, manager_address=manager_address, tmp_dir=tmp_dir,
            **kwargs)

        child_connection = process_manager_io.ChildConnection(request_in, response_out)
        rc = impl.main(child_connection)

        frames = sys._current_frames()  # pylint: disable=protected-access
        for thread in threading.enumerate():
            if thread.ident == threading.get_ident():
                continue
            logger.warning("Left over thread %s (%x)", thread.name, thread.ident)
            if thread.ident in frames:
                logger.warning("".join(traceback.format_stack(frames[thread.ident])))

    except SystemExit as exc:
        rc = exc.code
    except:  # pylint: disable=bare-except
        traceback.print_exc()
        rc = 1
    finally:
        rc = rc or 0
        sys.stdout.write("_exit(%d)\n" % rc)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(rc)  # pylint: disable=protected-access
