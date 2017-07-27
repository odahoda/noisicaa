#!/usr/bin/python3


class Mutation(object):
    pass


class AddNode(Mutation):
    def __init__(self, node_type, **args):
        super().__init__()
        self.node_type = node_type
        self.args = args

    def __str__(self):
        return '<AddNode type=%s%s>' % (
            self.node_type,
            ''.join(' %s=%r' % (k, v)
                     for k, v in sorted(self.args.items())))


class RemoveNode(Mutation):
    def __init__(self, node_id):
        super().__init__()
        self.node_id = node_id

    def __str__(self):
        return '<RemoveNode id=%s>' % self.node_id


class ConnectPorts(Mutation):
    def __init__(self, src_node, src_port, dest_node, dest_port):
        super().__init__()
        self.src_node = src_node
        self.src_port = src_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    def __str__(self):
        return '<ConnectPorts src=%s:%s dest=%s:%s>' % (
            self.src_node, self.src_port, self.dest_node, self.dest_port)


class DisconnectPorts(Mutation):
    def __init__(self, src_node, src_port, dest_node, dest_port):
        super().__init__()
        self.src_node = src_node
        self.src_port = src_port
        self.dest_node = dest_node
        self.dest_port = dest_port

    def __str__(self):
        return '<DisconnectPorts src=%s:%s dest=%s:%s>' % (
            self.src_node, self.src_port, self.dest_node, self.dest_port)


class SetPortProperty(Mutation):
    def __init__(self, node, port, **kwargs):
        super().__init__()
        self.node = node
        self.port = port
        self.kwargs = kwargs

    def __str__(self):
        return '<SetPortProperty port=%s:%s%s>' % (
            self.node, self.port,
            ''.join(' %s=%r' % (k, v)
                    for k, v in sorted(self.kwargs.items())))


class SetNodeParameter(Mutation):
    def __init__(self, node, **kwargs):
        super().__init__()
        self.node = node
        self.kwargs = kwargs

    def __str__(self):
        return '<SetNodeParameter node=%s%s>' % (
            self.node,
            ''.join(' %s=%r' % (k, v)
                    for k, v in sorted(self.kwargs.items())))
