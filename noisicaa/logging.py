#!/usr/bin/python3

import sys
import logging.handlers
from logging import *  # pylint: disable=W0614,W0401

class WrappingFormatter(Formatter):
    def formatMessage(self, record):
        record.message = record.message.replace('\n', '\n\t')
        return super().formatMessage(record)

def init(runtime_settings):
    captureWarnings(True)

    root_logger = getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    root_logger.setLevel(DEBUG)

    # Make loggers of 3rd party modules less noisy.
    for other in ('quamash', 'vext'):
        getLogger(other).setLevel(WARNING)

    log_level = {
        'debug': DEBUG,
        'info': INFO,
        'warning': WARNING,
        'error': ERROR,
        'critical': CRITICAL,
        }[runtime_settings.log_level]
    handler = StreamHandler(sys.stderr)
    handler.setLevel(log_level)
    handler.setFormatter(
        WrappingFormatter(
            '%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s'))

    root_logger.addHandler(handler)

    if runtime_settings.log_file:
        handler = logging.handlers.RotatingFileHandler(
            runtime_settings.log_file,
            maxBytes=10 * 2**20,
            backupCount=9,
            encoding='utf-8')
        handler.setLevel(DEBUG)
        handler.setFormatter(WrappingFormatter(
            '%(asctime)s\t%(levelname)s\t%(process)s\t%(thread)08x\t%(name)s\t%(message)s',
            '%Y%m%d-%H%M%S'))
        root_logger.addHandler(handler)
