#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node

logger = logging.getLogger(__name__)

class TrackControlSource(node.BuiltinNode):
    class_name = 'track_control_source'

    def __init__(self, *, track_id, **kwargs):
        super().__init__(**kwargs)

        self.track_id = track_id

    def add_to_spec(self, spec):
        super().add_to_spec(spec)

        spec.append_opcode('FETCH_BUFFER', 'track:' + self.track_id, self.outputs['out'].buf_name)
