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

from noisicaa import node_db

from .. import node

logger = logging.getLogger(__name__)


class Sink(node.BuiltinNode):
    class_name = 'sink'

    def __init__(self, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
            ])

        super().__init__(description=description, id='sink', **kwargs)

    def add_to_spec(self, spec):
        super().add_to_spec(spec)

        spec.append_opcode('OUTPUT', self.inputs['in:left'].buf_name, 'left')
        spec.append_opcode('OUTPUT', self.inputs['in:right'].buf_name, 'right')
