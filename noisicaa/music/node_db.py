#!/usr/bin/python3

from . import node_description


class NodeDB(object):
    def __init__(self):
        self._nodes = {}

        self._nodes['reverb'] = node_description.UserNodeDescription(
            display_name='Reverb',
            node_cls='csound_filter',
            ports=[
                node_description.AudioPortDescription(
                    name='in',
                    direction=node_description.PortDirection.Input),
                node_description.AudioPortDescription(
                    name='out',
                    direction=node_description.PortDirection.Output),
            ])

        self._nodes['compressor'] = node_description.UserNodeDescription(
            display_name='Compressor',
            node_cls='csound_filter',
            ports=[
                node_description.AudioPortDescription(
                    name='in',
                    direction=node_description.PortDirection.Input),
                node_description.AudioPortDescription(
                    name='out',
                    direction=node_description.PortDirection.Output),
            ])

    @property
    def nodes(self):
        return sorted(
            self._nodes.items(), key=lambda i: i[1].display_name)

    def get_node_description(self, label):
        return self._nodes[label]

