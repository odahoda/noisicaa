#!/usr/bin/python3

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

class PropertyValueChange(PropertyChange):
    def __init__(self, prop_name, old_value, new_value):
        super().__init__(prop_name)
        self.old_value = old_value
        self.new_value = new_value

class PropertyListChange(PropertyChange):
    pass

class PropertyListInsert(PropertyListChange):
    def __init__(self, prop_name, index, new_value):
        super().__init__(prop_name)
        self.index = index
        self.new_value = new_value

class PropertyListDelete(PropertyListChange):
    def __init__(self, prop_name, index, old_value):
        super().__init__(prop_name)
        self.index = index
        self.old_value = old_value

class PropertyListClear(PropertyListChange):
    def __init__(self, prop_name, old_values):
        super().__init__(prop_name)
        self.old_values = old_values


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
        old_value = instance.state.get(self.name, None)
        instance.state[self.name] = value
        if value != old_value:
            instance.property_changed(
                PropertyValueChange(self.name, old_value, value))

    def __delete__(self, instance):
        raise RuntimeError("You can't delete properties")

    def to_state(self, instance):
        raise NotImplementedError

    def from_state(self, instance, value):
        raise NotImplementedError


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

    def to_state(self, instance):
        return instance.state.get(self.name, self.default)

    def from_state(self, instance, value):
        instance.state[self.name] = value


class SimpleObjectList(object):
    def __init__(self, prop, instance):
        self._prop = prop
        self._instance = instance
        self._objs = []

    def _check_type(self, value):
        if not isinstance(value, self._prop.type):
            raise TypeError("Excepted %s" % self._prop.type)

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
        old_values = self._objs[:]
        self._objs.clear()
        self._instance.property_changed(
            PropertyListClear(self._prop.name, old_values))

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

    def to_state(self, instance):
        return list(instance.state.get(self.name, []))

    def from_state(self, instance, value):
        instance.state[self.name] = SimpleObjectList(self, instance)
        instance.state[self.name].extend(value)


class DictProperty(PropertyBase):
    def __get__(self, instance, owner):
        value = super().__get__(instance, owner)
        if value is None:
            value = {}
            super().__set__(instance, value)
        return value

    def __set__(self, instance, value):
        raise RuntimeError("DictProperty cannot be assigned.")

    def to_state(self, instance):
        return instance.state.get(self.name, {})

    def from_state(self, instance, value):
        instance.state[self.name] = value



class ObjectPropertyBase(PropertyBase):
    def __init__(self, cls):
        super().__init__()
        assert isinstance(cls, type)
        self.cls = cls

    def create(self, state):
        cls_name = state['__class__']
        if cls_name == self.cls.__name__:
            return self.cls(state=state)
        return self.cls.get_subclass(cls_name)(state=state)

    def to_state(self, instance):
        raise NotImplementedError

    def from_state(self, instance, value):
        raise NotImplementedError


class ObjectProperty(ObjectPropertyBase):
    def __set__(self, instance, value):
        logger.info("%s.%s=%s", type(instance), self.name, value)
        if value is not None and not self.cls.is_valid_subclass(value.__class__):
            raise TypeError(
                "Expected %s, got %s" % (
                    ', '.join(self.cls.get_valid_classes()),
                    value.__class__.__name__))

        current = self.__get__(instance, instance.__class__)
        if current is not None:
            current.detach()
            current.clear_parent_container()

        super().__set__(instance, value)

        if value is not None:
            value.attach(instance)
            value.set_parent_container(self)

    def to_state(self, instance):
        obj = instance.state.get(self.name, None)
        if obj is not None:
            assert isinstance(obj, ObjectBase)
            return obj.serialize()
        return None

    def from_state(self, instance, value):
        if value is not None:
            obj = self.create(value)
            obj.attach(instance)
            obj.set_parent_container(self)
            instance.state[self.name] = obj
        else:
            instance.state[self.name] = None

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
        old_children = self._objs[:]
        for obj in self._objs:
            obj.detach()
            obj.clear_parent_container()
        self._objs.clear()
        self._instance.property_changed(
            PropertyListClear(self._prop.name, old_children))


class ObjectListProperty(ObjectPropertyBase):
    def __get__(self, instance, owner):
        value = instance.state.get(self.name, None)
        if value is None:
            value = ObjectList(self, instance)
            instance.state[self.name] = value
        return value

    def __set__(self, instance, value):
        raise RuntimeError("ObjectListProperty cannot be assigned.")

    def to_state(self, instance):
        objs = instance.state.get(self.name, [])
        return [obj.serialize() for obj in objs]

    def from_state(self, instance, value):
        objs = ObjectList(self, instance)
        for s in value:
            obj = self.create(s)
            objs.append(obj)
        instance.state[self.name] = objs


class ObjectReferenceProperty(PropertyBase):
    def __init__(self, allow_none=False):
        super().__init__()
        self.allow_none = allow_none

    def __set__(self, instance, value):
        if value is None:
            if not self.allow_none:
                raise ValueError("None not allowed")
        elif not isinstance(value, ObjectBase):
            raise TypeError("Expected ObjectBase object")

        super().__set__(instance, value)

    def to_state(self, instance):
        obj = instance.state.get(self.name, None)
        if obj is not None:
            return 'ref:' + obj.id
        return None

    def from_state(self, instance, value):
        if value is not None:
            assert isinstance(value, str) and value.startswith('ref:')
            instance.state[self.name] = ('unresolved reference', value[4:])
        else:
            instance.state[self.name] = None


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

    _subclasses = {}

    def __init__(self):
        super().__init__()
        self.state = {}
        self._is_root = False
        self.parent = None
        self.__parent_container = None
        self.__index = None

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

    @classmethod
    def register_subclass(cls, subcls):
        ObjectBase._subclasses.setdefault(cls.__name__, {})[subcls.__name__] = subcls

    @classmethod
    def clear_subclass_registry(cls):
        ObjectBase._subclasses.clear()

    @classmethod
    def get_subclass(cls, name):
        return ObjectBase._subclasses[cls.__name__][name]

    @classmethod
    def is_valid_subclass(cls, subcls):
        if subcls.__name__ == cls.__name__:
            return True
        if cls.__name__ not in ObjectBase._subclasses:
            return False
        if subcls.__name__ in ObjectBase._subclasses[cls]:
            return True
        return False

    @classmethod
    def get_valid_classes(cls):
        return [cls.__name__] + sorted(
            ObjectBase._subclasses.get(cls.__name__, {}).keys())

    def set_parent_container(self, prop):
        self.__parent_container = prop

    def clear_parent_container(self):
        self.__parent_container = None
        self.__index = None

    def set_index(self, index):
        if self.__parent_container is None:
            raise ObjectNotAttachedError
        self.__index = index

    @property
    def index(self):
        if self.__parent_container is None:
            raise ObjectNotAttachedError
        assert self.__index is not None
        return self.__index

    @property
    def is_first(self):
        if self.__index is None:
            raise NotListMemberError
        return self.__index == 0

    @property
    def is_last(self):
        if self.__index is None:
            raise NotListMemberError
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

    def walk_children(self):
        yield self
        for child in self.list_children():
            yield from child.walk_children()
