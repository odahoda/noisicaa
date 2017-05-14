#!/usr/bin/python3


class PipelineVMSpec(object):
    def __init__(self):
        self.buffers = []
        self.nodes = []
        self.opcodes = []

    def dump(self):
        out = ''

        out += 'buffers:\n'
        for idx, buf in enumerate(self.buffers):
            out += '% 3d %s\n' % (idx, buf)

        out += 'nodes:\n'
        for idx, node_id in enumerate(self.nodes):
            out += '% 3d %s\n' % (idx, node_id)

        out += 'opcodes:\n'
        for idx, opcode in enumerate(self.opcodes):
            out += '% 3d %s\n' % (idx, opcode)

        return out


class OpCode(object):
    def __init__(self, op, **args):
        self.op = op
        self.args = args

    def __str__(self):
        return '%s(%s)' % (
            self.op,
            ', '.join(
                '%s=%r' % (k, v) for k, v in sorted(self.args.items())))
