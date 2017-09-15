#!/usr/bin/python3


class NodeDB(object):
    def __init__(self):
        self._db = {}

    def add(self, cls):
        assert cls.class_name is not None
        assert cls.class_name not in self._db
        self._db[cls.class_name] = cls

    def create(self, cls_name, host_data, **args):
        cls = self._db[cls_name]
        return cls(host_data=host_data, **args)

