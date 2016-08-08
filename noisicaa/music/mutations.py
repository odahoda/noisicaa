#!/usr/bin/python3

import logging

from noisicaa import core

logger = logging.getLogger(__name__)


class Mutation(object):
    def _prop2tuple(self, obj, prop):
        value = getattr(obj, prop.name, None)
        if isinstance(prop, core.ObjectProperty):
            return (
                prop.name,
                'obj',
                value.id if value is not None else None)

        elif isinstance(prop, core.ObjectListProperty):
            return (
                prop.name,
                'objlist',
                [v.id for v in value])

        elif isinstance(prop, core.ListProperty):
            return (prop.name, 'list', list(value))

        else:
            return (prop.name, 'scalar', value)


class SetProperties(Mutation):
    def __init__(self, obj, properties):
        self.id = obj.id
        self.properties = []
        for prop_name in properties:
            prop = obj.get_property(prop_name)
            self.properties.append(self._prop2tuple(obj, prop))

    def __str__(self):
        return '<SetProperties id="%s" %s>' % (
            self.id,
            ' '.join(
                '%s=%s:%r' % (p, t, v)
                for p, t, v in self.properties))


class AddObject(Mutation):
    def __init__(self, obj):
        self.id = obj.id
        self.cls = obj.SERIALIZED_CLASS_NAME or obj.__class__.__name__
        self.properties = []
        for prop in obj.list_properties():
            if prop.name == 'id':
                continue
            self.properties.append(self._prop2tuple(obj, prop))

    def __str__(self):
        return '<AddObject id=%s cls=%s %s>' % (
            self.id, self.cls,
            ' '.join(
                '%s=%s:%r' % (p, t, v)
                for p, t, v in self.properties))
    __repr__ = __str__


class ListInsert(Mutation):
    def __init__(self, obj, prop_name, index, value):
        self.id = obj.id
        self.prop_name = prop_name
        self.index = index
        prop = obj.get_property(prop_name)
        if isinstance(prop, core.ObjectListProperty):
            self.value_type = 'obj'
            self.value = value.id
        else:
            self.value_type = 'scalar'
            self.value = value

    def __str__(self):
        return '<ListInsert id=%s prop=%s index=%d value=%s:%s>' % (
            self.id, self.prop_name, self.index,
            self.value_type, self.value)
    __repr__ = __str__


class ListDelete(Mutation):
    def __init__(self, obj, prop_name, index):
        self.id = obj.id
        self.prop_name = prop_name
        self.index = index

    def __str__(self):
        return '<ListDelete id=%s prop=%s index=%d>' % (
            self.id, self.prop_name, self.index)


class PipelineMutation(Mutation):
    pass


class AddNode(PipelineMutation):
    def __init__(self, node_type, node_id, node_name, **args):
        self.node_type = node_type
        self.node_id = node_id
        self.node_name = node_name
        self.args = args

    def __str__(self):
        return '<AddNode type=%s id=%s name=%s%s>' % (
            self.node_type, self.node_id, self.node_name,
            ''.join(' %s=%r' % (k, v)
                     for k, v in sorted(self.args.items())))


class RemoveNode(PipelineMutation):
    def __init__(self, node_id):
        self.node_id = node_id

    def __str__(self):
        return '<RemoveNode id=%s>' % self.node_id


class ConnectPorts(PipelineMutation):
    def __init__(self, src_node, src_port, dest_node, dest_port):
        self.src_node = src_node
        self.src_port = src_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    def __str__(self):
        return '<ConnectPorts src=%s:%s dest=%s:%s>' % (
            self.src_node, self.src_port, self.dest_node, self.dest_port)


class DisconnectPorts(PipelineMutation):
    def __init__(self, src_node, src_port, dest_node, dest_port):
        self.src_node = src_node
        self.src_port = src_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    def __str__(self):
        return '<DisconnectPorts src=%s:%s dest=%s:%s>' % (
            self.src_node, self.src_port, self.dest_node, self.dest_port)


class SetPortProperty(PipelineMutation):
    def __init__(self, node, port, **kwargs):
        self.node = node
        self.port = port
        self.kwargs = kwargs

    def __str__(self):
        return '<SetPortProperty port=%s:%s%s>' % (
            self.node, self.port,
            ''.join(' %s=%r' % (k, v)
                    for k, v in sorted(self.kwargs.items())))
