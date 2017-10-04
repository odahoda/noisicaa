#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging
import traceback
import uuid

from noisicaa import core
from noisicaa.core import model_base

logger = logging.getLogger(__name__)

class StateBase(model_base.ObjectBase):
    SERIALIZED_CLASS_NAME = None

    cls_map = {}

    def __init__(self, state=None):
        self.listeners = core.CallbackRegistry()

        super().__init__()

        if state is not None:
            self.deserialize(state)
        else:
            self.id = uuid.uuid4().hex

        # logger.info("<%s id=%s> created (%s) by",
        #             type(self).__name__, self.id, id(self))
        # logger.info("%s", ''.join(traceback.format_list(traceback.extract_stack())))

    def __eq__(self, other):
        if self.__class__ is not other.__class__:
            return False
        for prop_name in self.list_property_names():
            if getattr(self, prop_name) != getattr(other, prop_name):
                return False
        return True

    @classmethod
    def register_class(cls, c):
        assert c.__name__ not in cls.cls_map
        cls.cls_map[c.__name__] = c

    @classmethod
    def clear_class_registry(cls):
        cls.cls_map.clear()

    def property_changed(self, change):
        self.listeners.call(change.prop_name, change)

        if not self.attached_to_root:
            return
        root = self.root
        root.listeners.call('model_changes', self, change)

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
            assert o.id is not None, o
            assert o.id not in self.__obj_map, (o.id, o)
            self.__obj_map[o.id] = o

        for o in obj.walk_children():
            for prop in o.list_properties():
                if isinstance(prop, model_base.ObjectReferenceProperty):
                    refid = prop.__get__(o, o.__class__)
                    if refid is not None and isinstance(refid, tuple):
                        assert refid[0] == 'unresolved reference'
                        refid = refid[1]
                        refobj = self.__obj_map[refid]
                        prop.__set__(o, refobj)

    def remove_object(self, obj):
        for o in obj.walk_children():
            assert o.id is not None, o
            assert o.id in self.__obj_map, (o.id, o)
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
                    if refid is not None and isinstance(refid, tuple):
                        assert refid[0] == 'unresolved reference'
                        refid = refid[1]
                        refobj = self.__obj_map[refid]
                        prop.__set__(node, refobj)

