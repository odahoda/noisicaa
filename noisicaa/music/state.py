#!/usr/bin/python3

import logging
import uuid

from noisicaa.core import model_base

logger = logging.getLogger(__name__)

class StateBase(model_base.ObjectBase):
    SERIALIZED_CLASS_NAME = None

    cls_map = {}

    def __init__(self, state=None):
        super().__init__()

        if state is not None:
            self.deserialize(state)
        else:
            self.id = uuid.uuid4().hex

    @classmethod
    def register_class(cls, c):
        assert c.__name__ not in cls.cls_map
        cls.cls_map[c.__name__] = c

    @classmethod
    def clear_class_registry(cls):
        cls.cls_map.clear()

    def property_changed(self, change):
        if not self.attached_to_root:
            return
        root = self.root
        if isinstance(change, model_base.PropertyValueChange):
            prop = self.get_property(change.prop_name)
            if isinstance(prop, model_base.ObjectProperty):
                mutation_type = 'update_objproperty'
            else:
                assert isinstance(
                    prop, (model_base.Property,
                           model_base.ObjectReferenceProperty,
                           model_base.DictProperty)), type(prop)
                mutation_type = 'update_property'

            root.handle_mutation(
                (mutation_type, self, change.prop_name,
                 change.old_value, change.new_value))

        elif isinstance(change, model_base.PropertyListChange):
            prop = self.get_property(change.prop_name)
            if isinstance(prop, model_base.ObjectListProperty):
                mutation_type = 'update_objlist'
            else:
                assert isinstance(prop, model_base.ListProperty)
                mutation_type = 'update_list'

            if isinstance(change, model_base.PropertyListInsert):
                root.handle_mutation(
                    (mutation_type, self, change.prop_name,
                     'insert', change.index, change.new_value))

            elif isinstance(change, model_base.PropertyListDelete):
                root.handle_mutation(
                    (mutation_type, self, change.prop_name,
                     'delete', change.index, change.old_value))

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
            if isinstance(prop, model_base.ObjectProperty):
                obj = prop.__get__(self, self.__class__)
                if obj is not None:
                    obj.reset_state()
                prop.__set__(self, None)
            elif isinstance(prop, model_base.ObjectListProperty):
                objs = prop.__get__(self, self.__class__)
                for obj in objs:
                    prop.__get__(self, self.__class__)
                    if obj is not None:
                        obj.reset_state()
                objs.clear()

        self.state = {'id': self.id}  # Don't forget my ID.

    def serialize(self):
        d = {'__class__': self.SERIALIZED_CLASS_NAME or self.__class__.__name__}
        for prop in self.list_properties():
            if isinstance(prop, model_base.Property):
                state = getattr(self, prop.name, prop.default)
            elif isinstance(prop, model_base.ListProperty):
                state = list(getattr(self, prop.name, []))
            elif isinstance(prop, model_base.DictProperty):
                state = dict(getattr(self, prop.name, {}))
            elif isinstance(prop, model_base.ObjectProperty):
                obj = getattr(self, prop.name, None)
                if obj is not None:
                    state = obj.serialize()
                else:
                    state = None
            elif isinstance(prop, model_base.ObjectListProperty):
                state = [
                    obj.serialize() for obj in getattr(self, prop.name)]
            elif isinstance(prop, model_base.ObjectReferenceProperty):
                obj = getattr(self, prop.name, None)
                if obj is not None:
                    state = 'ref:' + obj.id
                else:
                    state = None
            else:
                raise TypeError("Unknown property type %s" % type(prop))

            d[prop.name] = state

        return d

    def deserialize(self, state):
        for prop in self.list_properties():
            if prop.name not in state:
                # TODO: reset prop
                continue

            value = state[prop.name]
            if isinstance(prop, model_base.Property):
                setattr(self, prop.name, value)
            elif isinstance(prop, model_base.ListProperty):
                lst = getattr(self, prop.name)
                lst.clear()
                lst.extend(value)
            elif isinstance(prop, model_base.DictProperty):
                dct = getattr(self, prop.name)
                dct.clear()
                dct.update(value)
            elif isinstance(prop, model_base.ObjectProperty):
                if value is not None:
                    cls_name = value['__class__']
                    cls = self.cls_map[cls_name]
                    obj = cls(state=value)
                else:
                    obj = None
                setattr(self, prop.name, obj)
            elif isinstance(prop, model_base.ObjectListProperty):
                lst = getattr(self, prop.name)
                lst.clear()
                for v in value:
                    cls_name = v['__class__']
                    cls = self.cls_map[cls_name]
                    obj = cls(state=v)
                    lst.append(obj)
            elif isinstance(prop, model_base.ObjectReferenceProperty):
                if value is not None:
                    assert isinstance(value, str) and value.startswith('ref:')
                    self.state[prop.name] = ('unresolved reference', value[4:])
                else:
                    setattr(self, prop.name, None)
            else:
                raise TypeError("Unknown property type %s" % type(prop))


class RootMixin(object):
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

    def validate_object_map(self):
        obj_map = {}
        for o in self.walk_children():
            assert o.id is not None
            assert o.id not in obj_map, o
            obj_map[o.id] = o
        missing_objects = set(obj_map) - set(self.__obj_map)
        extra_objects = set(self.__obj_map) - set(obj_map)
        assert not missing_objects, missing_objects
        assert not extra_objects, extra_objects

    def init_references(self):
        self.__obj_map.clear()
        for node in self.walk_children():
            assert node.id not in self.__obj_map
            self.__obj_map[node.id] = node

        for node in self.walk_children():
            for prop in node.list_properties():
                if isinstance(prop, model_base.ObjectReferenceProperty):
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

