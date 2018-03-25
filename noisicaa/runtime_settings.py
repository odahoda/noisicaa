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

# mypy: loose


class RuntimeSettings(object):
    def __init__(self):
        self.dev_mode = False
        self.restart_on_crash = False
        self.start_clean = False
        self.log_level = 'warning'
        self.log_file = '/tmp/noisicaä.log'
        self.log_file_size = 10 * 2**20
        self.log_file_keep_old = 9

    def init_argparser(self, parser):
        parser.add_argument(
            '--dev-mode',
            dest='dev_mode', action='store_true',
            help="Run in developer mode.")
        parser.add_argument(
            '--no-dev-mode',
            dest='dev_mode', action='store_false',
            help="Run in end user mode.")
        parser.add_argument(
            '--restart-on-crash',
            dest='restart_on_crash', action='store_true',
            help="Restart UI when it crashes.")
        parser.add_argument(
            '--no-restart-on-crash',
            dest='restart_on_crash', action='store_false',
            help="Terminate when UI crashes.")
        parser.add_argument(
            '--start-clean',
            action='store_true',
            help="Start with clean settings.")
        parser.add_argument(
            '--log-level',
            default='error',
            help=("Minimum level for log messages written to STDERR. A comma separated list"
                  " of logger=level pairs, where 'logger' is the name of a logger and 'level'"
                  " one of 'debug', 'info', 'warning', 'error', 'critical'. A bare 'level'"
                  " applies to the root logger. E.g. 'error,noisicaa.ui=info' will print"
                  " INFO level logs for 'noisicaa.ui' and ERROR level for all other logger."))
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

        parser.set_defaults(dev_mode=True)

    def set_from_args(self, args):
        self.dev_mode = args.dev_mode
        self.restart_on_crash = args.restart_on_crash
        self.start_clean = args.start_clean
        self.log_level = args.log_level
        self.log_file = args.log_file
        self.log_file_size = args.log_file_size
        self.log_file_keep_old = args.log_file_keep_old
