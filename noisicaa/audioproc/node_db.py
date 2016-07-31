#!/usr/bin/python3


class NodeDB(object):
    def __init__(self):
        self._db = {}

    def add(self, cls):
        assert cls.desc.name not in self._db
        self._db[cls.desc.name] = cls

    @property
    def node_types(self):
        return sorted(
            (cls.desc for cls in self._db.values()),
            key=lambda desc: desc.name)

    def create(self, event_loop, name, args):
        cls = self._db[name]
        return cls(event_loop, **args)

