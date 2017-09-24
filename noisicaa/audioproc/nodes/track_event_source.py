#!/usr/bin/python3

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
