#!/usr/bin/python3

import logging
import uuid

logger = logging.getLogger(__name__)

class Error(Exception):
    pass

class ObjectNotAttachedError(Error):
    pass

class NotListMemberError(Error):
    pass


class PropertyChange(object):
    def __init__(self, prop_name):
        self.prop_name = prop_name

    def __str__(self, **kwargs):
        return '<%s%s>' % (type(self).__name__, ''.join(' %s=%r' % (k, v) for k, v in sorted(kwargs.items())))

class PropertyValueChange(PropertyChange):
    def __init__(self, prop_name, old_value, new_value):
        super().__init__(prop_name)
        self.old_value = old_value
        self.new_value = new_value

    def __str__(self):
        return super().__str__(old=self.old_value, new=self.new_value)

class PropertyListChange(PropertyChange):
    pass

class PropertyListInsert(PropertyListChange):
    def __init__(self, prop_name, index, new_value):
        super().__init__(prop_name)
        self.index = index
        self.new_value = new_value

    def __str__(self):
        return super().__str__(index=self.index, new=self.new_value)

class PropertyListDelete(PropertyListChange):
    def __init__(self, prop_name, index, old_value):
        super().__init__(prop_name)
        self.index = index
        self.old_value = old_value

    def __str__(self):
        return super().__str__(index=self.index, old=self.old_value)


class PropertyBase(object):
    def __init__(self, default=None):
        assert self.__class__ is not PropertyBase, "PropertyBase is abstract"
        self.name = None
        self.default = default

    def __get__(self, instance, owner):
        assert self.name is not None
        assert instance is not None
        assert owner is not None
        return instance.state.get(self.name, self.default)

    def __set__(self, instance, value):
        assert self.name is not None
        assert instance is not None
        old_value = instance.state.get(self.name, self.default)
        instance.state[self.name] = value
        if value != old_value:
            instance.property_changed(
                PropertyValueChange(self.name, old_value, value))

    def __delete__(self, instance):
        raise RuntimeError("You can't delete properties")


class Property(PropertyBase):
    def __init__(self, objtype, allow_none=False, default=None):
        super().__init__(default)
        self.type = objtype
        self.allow_none = allow_none

    def __set__(self, instance, value):
        if value is None:
            if not self.allow_none:
                raise ValueError("None not allowed")
        elif not isinstance(value, self.type):
            raise TypeError(
                "Excepted %s, got %s" % (
                    self.type.__name__, type(value).__name__))

        super().__set__(instance, value)


class SimpleObjectList(object):
    def __init__(self, prop, instance):
        self._prop = prop
        self._instance = instance
        self._objs = []

    def _check_type(self, value):
        if not isinstance(value, self._prop.type):
            raise TypeError(
                "Excepted %s, got %s" % (self._prop.type, type(value)))

    def __repr__(self):
        return '[%s]' % ', '.join(repr(e) for e in self._objs)

    def __len__(self):
        return len(self._objs)

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for a, b in zip(self._objs, other):
            if a != b:
                return False
        return True

    def __getitem__(self, idx):
        return self._objs[idx]

    def __setitem__(self, idx, obj):
        self._check_type(obj)
        self.__delitem__(idx)
        self.insert(idx, obj)

    def __delitem__(self, idx):
        old_value = self._objs[idx]
        del self._objs[idx]
        self._instance.property_changed(
            PropertyListDelete(self._prop.name, idx, old_value))

    def append(self, obj):
        self.insert(len(self._objs), obj)

    def insert(self, idx, obj):
        self._check_type(obj)
        self._objs.insert(idx, obj)
        self._instance.property_changed(
            PropertyListInsert(self._prop.name, idx, obj))

    def clear(self):
        while len(self._objs) > 0:
            self.__delitem__(0)

    def extend(self, value):
        for v in value:
            self.append(v)


class ListProperty(PropertyBase):
    def __init__(self, t):
        super().__init__()
        assert isinstance(t, type)
        assert not isinstance(t, ObjectBase)
        self.type = t

    def __get__(self, instance, owner):
        value = super().__get__(instance, owner)
        if value is None:
            value = SimpleObjectList(self, instance)
            instance.state[self.name] = value
        return value

    def __set__(self, instance, value):
        raise RuntimeError("ListProperty cannot be assigned.")


class DictProperty(PropertyBase):
    def __get__(self, instance, owner):
        value = super().__get__(instance, owner)
        if value is None:
            value = {}
            super().__set__(instance, value)
        return value

    def __set__(self, instance, value):
        raise RuntimeError("DictProperty cannot be assigned.")



class ObjectPropertyBase(PropertyBase):
    def __init__(self, cls):
        super().__init__()
        assert isinstance(cls, type)
        self.cls = cls


class ObjectProperty(ObjectPropertyBase):
    def __set__(self, instance, value):
        if value is not None and not isinstance(value, self.cls):
            raise TypeError(
                "Expected %s, got %s" % (
                    self.cls.__name__, type(value).__name__))

        current = self.__get__(instance, instance.__class__)
        if current is not None:
            if instance.attached_to_root:
                instance.root.remove_object(current)
            current.detach()
            current.clear_parent_container()

        super().__set__(instance, value)

        if value is not None:
            value.attach(instance)
            value.set_parent_container(self)
            if instance.attached_to_root:
                instance.root.add_object(value)


class ObjectList(object):
    def __init__(self, prop, instance):
        self._prop = prop
        self._instance = instance
        self._objs = []

    def __len__(self):
        return len(self._objs)

    def __getitem__(self, idx):
        return self._objs[idx]

    def __setitem__(self, idx, obj):
        self.__delitem__(idx)
        self.insert(idx, obj)

    def __delitem__(self, idx):
        old_child = self._objs[idx]
        old_child.detach()
        old_child.clear_parent_container()
        if self._instance.attached_to_root:
            self._instance.root.remove_object(old_child)
        del self._objs[idx]
        for i in range(idx, len(self._objs)):
            self._objs[i].set_index(i)
        self._instance.property_changed(
            PropertyListDelete(self._prop.name, idx, old_child))

    def append(self, obj):
        self.insert(len(self._objs), obj)

    def insert(self, idx, obj):
        obj.attach(self._instance)
        obj.set_parent_container(self)
        if self._instance.attached_to_root:
            self._instance.root.add_object(obj)
        self._objs.insert(idx, obj)
        for i in range(idx, len(self._objs)):
            self._objs[i].set_index(i)
        self._instance.property_changed(
            PropertyListInsert(self._prop.name, idx, obj))

    def clear(self):
        while len(self._objs) > 0:
            self.__delitem__(0)


class ObjectListProperty(ObjectPropertyBase):
    def __get__(self, instance, owner):
        value = instance.state.get(self.name, None)
        if value is None:
            value = ObjectList(self, instance)
            instance.state[self.name] = value
        return value

    def __set__(self, instance, value):
        raise RuntimeError("ObjectListProperty cannot be assigned.")


class DeferredReference(object):
    def __init__(self, obj_id):
        self._obj_id = obj_id
        self._props = []

    def add_reference(self, obj, prop):
        assert isinstance(prop, ObjectReferenceProperty)
        self._props.append((obj, prop))

    def dereference(self, target):
        assert isinstance(target, ObjectBase)
        assert target.id == self._obj_id
        for obj, prop in self._props:
            logger.debug(
                "Deferencing %s.%s = %s", obj.id, prop.name, target)
            prop.__set__(obj, target)


class ObjectReferenceProperty(PropertyBase):
    def __init__(self, allow_none=False):
        super().__init__()
        self.allow_none = allow_none

    def __set__(self, instance, value):
        if value is None:
            if not self.allow_none:
                raise ValueError("None not allowed")
        elif not isinstance(value, (ObjectBase, DeferredReference)):
            raise TypeError(
                "Expected ObjectBase or DeferredReference object, got %s"
                % type(value))

        current = self.__get__(instance, instance.__class__)
        if (current is not None
            and not isinstance(current, (tuple, DeferredReference))):
            assert current.ref_count > 0
            current.ref_count -= 1
            logger.info("refcount(%s) = %d", current.id, current.ref_count)

        super().__set__(instance, value)

        if value is not None and not isinstance(value, DeferredReference):
            value.ref_count += 1
            logger.info("refcount(%s) = %d", value.id, value.ref_count)


class ObjectMeta(type):
    def __new__(mcs, name, parents, dct):
        properties = []
        for k, v in dct.items():
            if isinstance(v, PropertyBase):
                assert v.name is None
                v.name = k
                properties.append(k)
        dct['properties'] = properties
        return super().__new__(mcs, name, parents, dct)


class ObjectBase(object, metaclass=ObjectMeta):
    id = Property(str, allow_none=False)

    def __init__(self):
        super().__init__()
        self.state = {}
        self._is_root = False
        self.parent = None
        self.__parent_container = None
        self.__index = None
        self.ref_count = 0

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        if self.state != other.state:
            return False
        return True

    @property
    def root(self):
        if self.parent is None:
            if self._is_root:
                return self
            raise ObjectNotAttachedError
        return self.parent.root

    @property
    def attached_to_root(self):
        if self.parent is None:
            return self._is_root
        return self.parent.attached_to_root

    def attach(self, parent):
        assert self.parent is None
        self.parent = parent

    def detach(self):
        assert self.parent is not None
        self.parent = None

    def is_child_of(self, parent):
        p = self.parent
        while p is not None:
            if p is parent:
                return True
            p = p.parent
        return False

    def set_parent_container(self, prop):
        self.__parent_container = prop

    def clear_parent_container(self):
        self.__parent_container = None
        self.__index = None

    def set_index(self, index):
        if self.__parent_container is None:
            raise ObjectNotAttachedError(self.id)
        self.__index = index

    @property
    def index(self):
        if self.__parent_container is None:
            raise ObjectNotAttachedError(self.id)
        assert self.__index is not None
        return self.__index

    @property
    def is_first(self):
        if self.__index is None:
            raise NotListMemberError(self.id)
        return self.__index == 0

    @property
    def is_last(self):
        if self.__index is None:
            raise NotListMemberError(self.id)
        return self.__index == len(self.__parent_container) - 1

    @property
    def prev_sibling(self):
        if self.is_first:
            raise IndexError("First list member has no previous sibling.")
        return self.__parent_container[self.index - 1]

    @property
    def next_sibling(self):
        if self.is_last:
            raise IndexError("Last list member has no next sibling.")
        return self.__parent_container[self.index + 1]

    def get_property(self, prop_name):
        for cls in self.__class__.__mro__:
            if not issubclass(cls, ObjectBase):
                continue
            try:
                prop = cls.__dict__[prop_name]
            except KeyError:
                continue
            assert isinstance(prop, PropertyBase)
            return prop
        raise AttributeError("%s has not property %s" % (self.__class__.__name__, prop_name))

    def list_properties(self):
        for cls in self.__class__.__mro__:
            if not issubclass(cls, ObjectBase):
                continue
            for k in cls.properties:
                prop = cls.__dict__[k]
                assert prop.name == k
                yield prop

    def list_property_names(self):
        for prop in self.list_properties():
            yield prop.name

    def property_changes(self, change):
        print(change)

    def list_children(self):
        for prop in self.list_properties():
            if isinstance(prop, ObjectProperty):
                obj = prop.__get__(self, self.__class__)
                if obj is not None:
                    yield obj
            elif isinstance(prop, ObjectListProperty):
                yield from prop.__get__(self, self.__class__)

    def walk_children(self, topdown=True):
        if topdown:
            yield self
        for child in self.list_children():
            yield from child.walk_children(topdown)
        if not topdown:
            yield self
