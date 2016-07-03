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


class UpdateObjectList(Mutation):
    def __init__(self, obj, prop_name, *args):
        self.id = obj.id
        self.prop_name = prop_name
        self.args = args

    def __str__(self):
        return '<UpdateObjectList id=%s prop=%s %s>' % (
            self.id, self.prop_name,
            ' '.join(repr(a) for a in self.args))

class UpdateList(Mutation):
    def __init__(self, obj, prop_name, *args):
        self.id = obj.id
        self.prop_name = prop_name
        self.args = args

    def __str__(self):
        return '<UpdateList id=%s prop=%s %s>' % (
            self.id, self.prop_name,
            ' '.join(repr(a) for a in self.args))

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


class ConnectPorts(PipelineMutation):
    def __init__(self, src_node, src_port, dest_node, dest_port):
        self.src_node = src_node
        self.src_port = src_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    def __str__(self):
        return '<ConnectPorts src=%s:%s dest=%s:%s>' % (
            self.src_node, self.src_port, self.dest_node, self.dest_port)
