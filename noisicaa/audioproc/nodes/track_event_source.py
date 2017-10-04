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
import random

from noisicaa import core
from noisicaa import music
from noisicaa import node_db
from .. import ports
from .. import node
from .. import vm

logger = logging.getLogger(__name__)


class TrackEventSource(node.BuiltinNode):
    class_name = 'track_event_source'

    def __init__(self, *, track_id, **kwargs):
        super().__init__(**kwargs)

        self.track_id = track_id

    def add_to_spec(self, spec):
        super().add_to_spec(spec)

        spec.append_opcode('FETCH_BUFFER', 'track:' + self.track_id, self.outputs['out'].buf_name)

        spec.append_buffer(self.id + ':messages', vm.AtomData())
        spec.append_opcode(
            'FETCH_MESSAGES',
            core.build_labelset({core.MessageKey.trackId: self.track_id}).to_bytes(),
            self.id + ':messages')
        spec.append_opcode('MIX', self.id + ':messages', self.outputs['out'].buf_name)
