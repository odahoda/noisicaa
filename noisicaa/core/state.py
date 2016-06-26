#!/usr/bin/python3

import logging
import uuid

from . import model_base

# fix imports if properties
from .model_base import *

logger = logging.getLogger(__name__)

class StateBase(model_base.ObjectBase):
    def __init__(self, state=None):
        super().__init__()

        if state is not None:
            self.deserialize(state)
        else:
            self.id = uuid.uuid4().hex

    def property_changed(self, change):
        if not self.attached_to_root:
            return
        root = self.root
        if isinstance(change, model_base.PropertyValueChange):
            root.handle_mutation(
                ('update_property', self, change.prop_name,
                 change.old_value, change.new_value))


        elif isinstance(change, model_base.PropertyListChange):
            prop = self.get_property(change.prop_name)
            if isinstance(prop, ObjectListProperty):
                mutation_type = 'update_objlist'
            else:
                assert isinstance(prop, ListProperty)
                mutation_type = 'update_list'

            if isinstance(change, model_base.PropertyListInsert):
                root.handle_mutation(
                    (mutation_type, self, change.prop_name,
                     'insert', change.index, change.new_value))

            elif isinstance(change, model_base.PropertyListDelete):
                root.handle_mutation(
                    (mutation_type, self, change.prop_name,
                     'delete', change.index))

            elif isinstance(change, model_base.PropertyListClear):
                root.handle_mutation(
                    (mutation_type, self, change.prop_name,
                     'clear'))

            else:
                raise TypeError(
                    "Unsupported change type %s" % type(change))

        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def reset_state(self):
        for prop in self.list_properties():
            if isinstance(prop, ObjectProperty):
                obj = prop.__get__(self, self.__class__)
                if obj is not None:
                    obj.reset_state()
                prop.__set__(self, None)
            elif isinstance(prop, ObjectListProperty):
                objs = prop.__get__(self, self.__class__)
                for obj in objs:
                    prop.__get__(self, self.__class__)
                    if obj is not None:
                        obj.reset_state()
                objs.clear()

        self.state = {'id': self.id}  # Don't forget my ID.

    def serialize(self):
        d = {'__class__': self.__class__.__name__}
        for prop in self.list_properties():
            d[prop.name] = prop.to_state(self)

        return d

    def deserialize(self, state):
        for prop in self.list_properties():
            if prop.name not in state:
                continue
            prop.from_state(self, state[prop.name])

    @classmethod
    def create_from_state(cls, state):
        cls_name = state['__class__']
        if cls_name == cls.__name__:
            return cls(state=state)
        return cls.get_subclass(cls_name)(state=state)


class RootObject(StateBase):
    def __init__(self, state=None):
        super().__init__(state=state)

        self.__obj_map = {self.id: self}
        self._is_root = True

    def get_object(self, obj_id):
        return self.__obj_map[obj_id]

    def add_object(self, obj):
        for o in obj.walk_children():
            assert o.id is not None
            assert o.id not in self.__obj_map
            self.__obj_map[o.id] = o

    def remove_object(self, obj):
        for o in obj.walk_children():
            assert o.id is not None
            assert o.id in self.__obj_map, o
            del self.__obj_map[o.id]

    def init_references(self):
        self.__obj_map.clear()
        for node in self.walk_children():
            assert node.id not in self.__obj_map
            self.__obj_map[node.id] = node

        for node in self.walk_children():
            for prop in node.list_properties():
                if isinstance(prop, ObjectReferenceProperty):
                    refid = prop.__get__(node, node.__class__)
                    if refid is not None:
                        assert isinstance(refid, tuple)
                        assert refid[0] == 'unresolved reference'
                        refid = refid[1]
                        refobj = self.__obj_map[refid]
                        prop.__set__(node, refobj)

    # TODO: take (obj, PropertyChange) args
    def handle_mutation(self, mutation):
        pass

