#!/usr/bin/python3

import logging

logger = logging.getLogger(__name__)


class Selectable(object):
    selection_class = None


class SelectionSet(object):
    def __init__(self):
        self.__selection_set = set()

    def __iter__(self):
        yield from self.__selection_set

    def empty(self):
        return len(self.__selection_set) == 0

    def clear(self):
        for obj in self.__selection_set:
            obj.setSelected(False)
        self.__selection_set.clear()

    def add(self, obj):
        if obj in self.__selection_set:
            raise RuntimeError("Item already selected.")

        logger.info("Adding to selection: %s", obj)

        # TODO: Allow multiple selection.
        self.clear()

        assert obj.selection_class is not None

        self.__selection_set.add(obj)
        obj.setSelected(True)

    def remove(self, obj, update_object=True):
        if obj not in self.__selection_set:
            raise RuntimeError("Item not selected.")

        logger.info("Removing selection: %s", obj)

        self.__selection_set.remove(obj)
        if update_object:
            obj.setSelected(False)

