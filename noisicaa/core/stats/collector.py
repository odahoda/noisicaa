#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import logging

from . import timeseries

logger = logging.getLogger(__name__)


class Collector(object):
    def __init__(self, timeseries_length=60*10*10):
        self.__timeseries = timeseries.TimeseriesSet()
        self.__timeseries_length = timeseries_length

    def add_value(self, name, value):
        ts = self.__timeseries.setdefault(name, timeseries.Timeseries())
        ts.insert(0, value)

        drop_count = len(ts) - self.__timeseries_length
        if drop_count > 0:
            del ts[-drop_count:]

    def collect(self, registry):
        for name, value in registry.collect():
            self.add_value(name, value)

    def evaluate_expression(self, expr):
        result = self.__timeseries

        for op, *args in expr:
            if op == 'SELECT':
                result = result.select(args[0])
            elif op == 'RATE':
                result = result.rate()
            else:
                raise ValueError(op)

        return result

    def list_stats(self):
        return list(sorted(self.__timeseries.keys()))

    def fetch_stats(self, expressions):
        return {
            id: self.evaluate_expression(expr)
            for id, expr in expressions.items()}

    def dump(self):
        for name, ts in sorted(self.__timeseries.items()):
            logger.info("%s = %s", name, ts.latest())
