#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node

logger = logging.getLogger(__name__)

class TrackAudioSource(node.BuiltinNode):
    class_name = 'track_audio_source'

    def __init__(self, *, track_id, **kwargs):
        super().__init__(**kwargs)

        self.track_id = track_id

    def add_to_spec(self, spec):
        super().add_to_spec(spec)

        spec.append_opcode(
            'FETCH_BUFFER', 'track:' + self.track_id + ':left', self.outputs['out:left'].buf_name)
        spec.append_opcode(
            'FETCH_BUFFER', 'track:' + self.track_id + ':right', self.outputs['out:right'].buf_name)
