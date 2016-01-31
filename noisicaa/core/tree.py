#!/usr/bin/python3

class TreeNode(object):
    def __init__(self):
        super().__init__()

        self.parent = None

    @property
    def root(self):
        if self.parent is None:
            return self
        return self.parent.root

    def list_children(self):
        yield from []

    def attach(self, parent):
        assert self.parent is None
        self.parent = parent

    def detach(self):
        assert self.parent is not None
        self.parent = None

