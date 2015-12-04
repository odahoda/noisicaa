#!/usr/bin/python3

import logging
import uuid

from .tree import TreeNode

logger = logging.getLogger(__name__)


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
            for listener in instance.get_change_listeners(self.name):
                listener(old_value, value)

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
        del self._objs[idx]

        for listener in self._instance.get_change_listeners(self._prop.name):
            listener('delete', idx)

    def append(self, obj):
        self.insert(len(self._objs), obj)

    def insert(self, idx, obj):
        self._check_type(obj)
        self._objs.insert(idx, obj)

        for listener in self._instance.get_change_listeners(self._prop.name):
            listener('insert', idx, obj)

    def clear(self):
        self._objs.clear()

        for listener in self._instance.get_change_listeners(self._prop.name):
            listener('clear')

    def extend(self, value):
        for v in value:
            self.append(v)


class ListProperty(PropertyBase):
    def __init__(self, t):
        super().__init__()
        assert isinstance(t, type)
        assert not isinstance(t, StateBase)
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
        if value is not None and not self.cls.is_valid_subclass(value.__class__):
            raise TypeError(
                "Expected %s, got %s" % (
                    ', '.join(self.cls.get_valid_classes()),
                    value.__class__.__name__))

        current = self.__get__(instance, instance.__class__)
        if current is not None:
            current.detach()
        super().__set__(instance, value)
        if value is not None:
            value.attach(instance)

    def to_state(self, instance):
        obj = instance.state.get(self.name, None)
        if obj is not None:
            assert isinstance(obj, StateBase)
            return obj.serialize()
        return None

    def from_state(self, instance, value):
        if value is not None:
            obj = self.create(value)
            obj.attach(instance)
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
        self._objs[idx].detach()
        del self._objs[idx]

        for listener in self._instance.get_change_listeners(self._prop.name):
            listener('delete', idx)

    def append(self, obj):
        self.insert(len(self._objs), obj)

    def insert(self, idx, obj):
        obj.attach(self._instance)
        self._objs.insert(idx, obj)

        for listener in self._instance.get_change_listeners(self._prop.name):
            listener('insert', idx, obj)

    def clear(self):
        for obj in self._objs:
            obj.detach()
        self._objs.clear()

        for listener in self._instance.get_change_listeners(self._prop.name):
            listener('clear')


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
        elif not isinstance(value, StateBase):
            raise TypeError("Expected StateBase object")

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


class StateMeta(type):
    def __new__(mcs, name, parents, dct):
        properties = []
        for k, v in dct.items():
            if isinstance(v, PropertyBase):
                assert v.name is None
                v.name = k
                properties.append(k)
        dct['properties'] = properties
        return super().__new__(mcs, name, parents, dct)


class StateBase(TreeNode, metaclass=StateMeta):
    id = Property(str)

    _subclasses = {}

    def __init__(self):
        super().__init__()
        self.state = {}
        self.__listeners = {}

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        if self.state != other.state:
            return False
        return True

    @classmethod
    def register_subclass(cls, subcls):
        StateBase._subclasses.setdefault(cls, {})[subcls.__name__] = subcls

    @classmethod
    def get_subclass(cls, name):
        return StateBase._subclasses[cls][name]

    @classmethod
    def is_valid_subclass(cls, subcls):
        if subcls is cls:
            return True
        if cls not in StateBase._subclasses:
            return False
        if subcls.__name__ in StateBase._subclasses[cls]:
            return True
        return False

    @classmethod
    def get_valid_classes(cls):
        return [cls.__name__] + list(sorted(StateBase._subclasses.items()))

    def list_properties(self):
        for cls in self.__class__.__mro__:
            if not issubclass(cls, StateBase):
                continue
            for k in cls.properties:
                prop = cls.__dict__[k]
                assert prop.name == k
                yield prop

    def list_property_names(self):
        for prop in self.list_properties():
            yield prop.name

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

    def init_state(self, state):
        if state is not None:
            self.deserialize(state)
        else:
            self.id = uuid.uuid4().hex

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

        self.state = {}

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

    def init_references(self):
        all_objects = {}
        for node in self.walk_children():
            assert node.id not in all_objects
            all_objects[node.id] = node

        for node in self.walk_children():
            for prop in node.list_properties():
                if isinstance(prop, ObjectReferenceProperty):
                    refid = prop.__get__(node, node.__class__)
                    if refid is not None:
                        assert isinstance(refid, tuple)
                        assert refid[0] == 'unresolved reference'
                        refid = refid[1]
                        refobj = all_objects[refid]
                        prop.__set__(node, refobj)

    def get_change_listeners(self, prop_name):
        return self.__listeners.get(prop_name, [])

    def add_change_listener(self, prop_name, listener):
        if listener in self.__listeners.get(prop_name, []):
            raise ValueError("Listener already registered.")

        for prop in self.list_properties():
            if prop.name == prop_name:
                logger.info("Add listener %s for property %s to %s",
                            listener, prop_name, self)
                self.__listeners.setdefault(prop_name, []).append(listener)
                break
        else:
            raise ValueError("Invalid property %s" % prop_name)

    def remove_change_listener(self, prop_name, listener):
        if listener not in self.__listeners.get(prop_name, []):
            raise ValueError("Listener is not registered.")

        logger.info("Remove listener %s for property %s from %s",
                    listener, prop_name, self)
        self.__listeners[prop_name].remove(listener)
        if len(self.__listeners[prop_name]) == 0:
            del self.__listeners[prop_name]
