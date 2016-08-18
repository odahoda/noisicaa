#!/usr/bin/python3

import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations

logger = logging.getLogger(__name__)


class PipelineGraphNode(model.PipelineGraphNode, state.StateBase):
    def __init__(
            self, name=None, graph_pos_x=None, graph_pos_y=None,
            state=None):
        super().__init__(state)

        if state is None:
            self.name = name
            self.graph_pos_x = graph_pos_x
            self.graph_pos_y = graph_pos_y

    @property
    def sheet(self):
        return self.sheet

    @property
    def project(self):
        return self.sheet.parent

state.StateBase.register_class(PipelineGraphNode)


class PipelineGraphConnection(
        model.PipelineGraphConnection, state.StateBase):
    def __init__(self, source_node=None, dest_node=None, state=None):
        super().__init__(state)

        if state is None:
            self.source_node = source_node
            self.dest_node = dest_node

    @property
    def sheet(self):
        return self.sheet

    @property
    def project(self):
        return self.sheet.parent

state.StateBase.register_class(PipelineGraphConnection)
