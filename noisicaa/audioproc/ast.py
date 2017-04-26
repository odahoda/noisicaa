#!/usr/bin/python3


class ASTNode(object):
    def __init__(self):
        self.children = []

    def __str__(self):
        return type(self).__name__

    def dump(self, indent=0):
        out = '  ' * indent + str(self) + '\n'
        for child in self.children:
            out += child.dump(indent + 1)
        return out

    def walk(self):
        yield self
        yield from self.children


class Sequence(ASTNode):
    pass


class CallNode(ASTNode):
    def __init__(self, node_id):
        super().__init__()

        self.node_id = node_id

    def __str__(self):
        return '%s(%s)' % (super().__str__(), self.node_id)


class OutputStereo(ASTNode):
    pass
