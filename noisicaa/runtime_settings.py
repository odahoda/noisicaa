#!/usr/bin/python3

import json

class RuntimeSettings(object):
    def __init__(self):
        self.dev_mode = False
        self.start_clean = False
        self.log_level = 'warning'
        self.log_file = '/tmp/noisicaä.log'
        self.log_file_size = 10 * 2**20
        self.log_file_keep_old = 9

    def init_argparser(self, parser):
        parser.add_argument(
            '--dev-mode',
            action='store_true',
            help="Run in developer mode.")
        parser.add_argument(
            '--start-clean',
            action='store_true',
            help="Start with clean settings.")
        parser.add_argument(
            '--log-level',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            default='error',
            help="Minimum level for log messages written to STDERR.")
        parser.add_argument(
            '--log-file',
            default='/tmp/noisicaä.log',
            metavar="PATH",
            help="Write log to file.")
        parser.add_argument(
            '--log-file-size',
            type=int,
            default=10*2**20,
            metavar="BYTES",
            help="Maximum size of the log file.")
        parser.add_argument(
            '--log-file-keep-old',
            type=int,
            default=9,
            metavar="NUM",
            help="Number of old log files to keep.")
        parser.add_argument(
            '--runtime-settings',
            type=str,
            metavar="JSON",
            help=("JSON object with runtime settings. If set, other"
                  " flags are ignored."))

    def set_from_args(self, args):
        if args.runtime_settings:
            self.from_json(json.loads(args.runtime_settings))
        else:
            self.dev_mode = args.dev_mode
            self.start_clean = args.start_clean
            self.log_level = args.log_level
            self.log_file = args.log_file
            self.log_file_size = args.log_file_size
            self.log_file_keep_old = args.log_file_keep_old

    def as_args(self):
        return ['--runtime-settings', json.dumps(self.to_json())]

    def to_json(self):
        return {
            'dev_mode': self.dev_mode,
            'start_clean': self.start_clean,
            'log_level': self.log_level,
            'log_file': self.log_file,
            'log_file_size': self.log_file_size,
            'log_file_keep_old': self.log_file_keep_old,
            }

    def from_json(self, j):
        if 'dev_mode' in j:
            self.dev_mode = j['dev_mode']
        if 'start_clean' in j:
            self.start_clean = j['start_clean']
        if 'log_level' in j:
            self.log_level = j['log_level']
        if 'log_file' in j:
            self.log_file = j['log_file']
        if 'log_file_size' in j:
            self.log_file_size = j['log_file_size']
        if 'log_file_keep_old' in j:
            self.log_file_keep_old = j['log_file_keep_old']
