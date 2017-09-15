#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node
from ..vm import ast

logger = logging.getLogger(__name__)

class TrackAudioSource(node.BuiltinNode):
    class_name = 'track_audio_source'

    def __init__(self, *, track_id, **kwargs):
        super().__init__(**kwargs)

        self.track_id = track_id

    def get_ast(self):
        seq = super().get_ast()
        seq.add(ast.FetchBuffer(
            'track:' + self.track_id + ':left',
            self.outputs['out:left'].buf_name))
        seq.add(ast.FetchBuffer(
            'track:' + self.track_id + ':right',
            self.outputs['out:right'].buf_name))

        return seq
