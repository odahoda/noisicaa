#!/usr/bin/python3

import logging
import random

import noisicore
from noisicaa import core
from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from ..vm import ast

logger = logging.getLogger(__name__)


class TrackEventSource(node.BuiltinNode):
    class_name = 'track_event_source'

    def __init__(self, *, track_id, **kwargs):
        super().__init__(**kwargs)

        self.track_id = track_id

    def get_ast(self):
        seq = super().get_ast()
        seq.add(ast.FetchBuffer(
            'track:' + self.track_id,
            self.outputs['out'].buf_name))

        # seq.add(ast.LogAtom(
        #     self.outputs['out'].buf_name))

        # TODO: reanimate
        # seq.add(ast.AllocBuffer(
        #     self.id + ':messages', noisicore.AtomData()))
        # seq.add(ast.FetchMessages(
        #     core.build_labelset({core.MessageKey.trackId: self.track_id}),
        #     self.id + ':messages'))
        # seq.add(ast.MixBuffers(
        #     self.id + ':messages', self.outputs['out'].buf_name))

        return seq
