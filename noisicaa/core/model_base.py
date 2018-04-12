#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import (  # pylint: disable=unused-import
    cast, overload,
    Any, Optional, Union,
    Dict, List, Tuple, Type,
    Sequence, MutableSequence, Iterable, Iterator,
    Generic, TypeVar
)

logger = logging.getLogger(__name__)


class Error(Exception):
    pass

class ObjectNotAttachedError(Error):
    def __init__(self, obj: 'ObjectBase') -> None:
        super().__init__(str(obj))


class NotListMemberError(Error):
    pass


class PropertyChange(object):
    def __init__(self, prop_name: str) -> None:
        self.prop_name = prop_name

    def _fmt(self, **kwargs: Any) -> str:
        return '<%s%s>' % (
            type(self).__name__, ''.join(' %s=%r' % (k, v) for k, v in sorted(kwargs.items())))

    def __str__(self) -> str:
        return self._fmt()


class PropertyValueChange(PropertyChange):
    def __init__(self, prop_name: str, old_value: Any, new_value: Any) -> None:
        super().__init__(prop_name)
        self.old_value = old_value
        self.new_value = new_value

    def __str__(self) -> str:
        return self._fmt(old=self.old_value, new=self.new_value)


class PropertyListChange(PropertyChange):
    pass


class PropertyListInsert(PropertyListChange):
    def __init__(self, prop_name: str, index: int, new_value: Any) -> None:
        super().__init__(prop_name)
        self.index = index
        self.new_value = new_value

    def __str__(self) -> str:
        return self._fmt(index=self.index, new=self.new_value)


class PropertyListDelete(PropertyListChange):
    def __init__(self, prop_name: str, index: int, old_value: Any) -> None:
        super().__init__(prop_name)
        self.index = index
        self.old_value = old_value

    def __str__(self) -> str:
        return self._fmt(index=self.index, old=self.old_value)


PROPTYPE = TypeVar('PROPTYPE')
class PropertyBase(Generic[PROPTYPE]):
    def __init__(self, default: Optional[PROPTYPE] = None) -> None:
        assert self.__class__ is not PropertyBase, "PropertyBase is abstract"
        self.name = None  # type: str
        self.default = default

    def get_value(self, instance: Optional['ObjectBase']) -> PROPTYPE:
        return instance.state.get(self.name, self.default)

    def set_value(self, instance: 'ObjectBase', value: PROPTYPE) -> None:
        old_value = instance.state.get(self.name, self.default)
        instance.state[self.name] = value
        if value != old_value:
            instance.property_changed(PropertyValueChange(self.name, old_value, value))

    def __get__(self, instance: Optional['ObjectBase'], owner: Type['ObjectBase']) -> PROPTYPE:
        assert instance is not None
        assert owner is not None
        return self.get_value(instance)

    def __set__(self, instance: 'ObjectBase', value: PROPTYPE) -> None:
        assert self.name is not None
        assert instance is not None
        self.set_value(instance, value)

    def __delete__(self, instance: 'ObjectBase') -> None:
        raise RuntimeError("You can't delete properties")


class Property(PropertyBase[PROPTYPE]):
    def __init__(
            self, *objtypes: Type[PROPTYPE], allow_none: bool = False,
            default: Optional[PROPTYPE] = None) -> None:
        super().__init__(default)
        if not objtypes or not all(isinstance(t, type) for t in objtypes):
            raise TypeError("Expected one or more types.")

        self.type = tuple(objtypes)

        self.allow_none = allow_none

    def set_value(self, instance: 'ObjectBase', value: PROPTYPE) -> None:
        if value is None:
            if not self.allow_none:
                raise ValueError("None not allowed")
        elif not isinstance(value, self.type):
            raise TypeError(
                "Excepted %s, got %s" % (
                    ', '.join(t.__name__ for t in self.type), type(value).__name__))

        super().set_value(instance, value)


class SimpleObjectList(MutableSequence[PROPTYPE]):
    def __init__(self, t: Type[PROPTYPE], name: str, instance: 'ObjectBase') -> None:
        self._type = t
        self._name = name
        self._instance = instance
        self._objs = []  # type: List[PROPTYPE]

    def _check_type(self, value: Any) -> None:
        if not isinstance(value, self._type):
            raise TypeError(
                "Excepted %s, got %s" % (self._type, type(value)))

    def __repr__(self) -> str:
        return '[%s]' % ', '.join(repr(e) for e in self._objs)

    def __len__(self) -> int:
        return len(self._objs)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, (list, SimpleObjectList)):
            return False
        if len(self) != len(other):
            return False
        for a, b in zip(self._objs, other):
            if a != b:
                return False
        return True

    # pylint: disable=function-redefined,multiple-statements,pointless-statement
    @overload
    def __getitem__(self, idx: int) -> PROPTYPE:
        pass
    @overload
    def __getitem__(self, idx: slice) -> Sequence[PROPTYPE]:
        pass
    def __getitem__(self, idx: Union[int, slice]) -> Any:
        return self._objs[idx]

    @overload
    def __setitem__(self, idx: int, obj: PROPTYPE) -> None:
        pass
    @overload
    def __setitem__(self, idx: slice, obj: Iterable[PROPTYPE]) -> None:
        pass
    def __setitem__(self, idx: Union[int, slice], obj: Union[PROPTYPE, Iterable[PROPTYPE]]) -> None:
        if isinstance(idx, slice):
            idx = cast(slice, idx)
            obj = cast(Iterable[PROPTYPE], obj)
            for i, o in zip(range(idx.start, idx.stop, idx.step), obj):
                self._check_type(o)
                self.__delitem__(i)
                self.insert(i, o)
        elif isinstance(idx, int):
            idx = cast(int, idx)
            obj = cast(PROPTYPE, obj)
            self._check_type(obj)
            self.__delitem__(idx)
            self.insert(idx, obj)
        else:
            raise TypeError(idx)

    @overload
    def __delitem__(self, idx: int) -> None:
        pass
    @overload
    def __delitem__(self, idx: slice) -> None:
        pass
    def __delitem__(self, idx: Union[int, slice]) -> None:
        if isinstance(idx, slice):
            raise NotImplementedError
        else:
            old_value = self._objs[idx]
            del self._objs[idx]
            self._instance.property_changed(PropertyListDelete(self._name, idx, old_value))
    # pylint: enable=function-redefined,multiple-statements,pointless-statement

    def append(self, obj: PROPTYPE) -> None:
        self.insert(len(self._objs), obj)

    def insert(self, idx: int, obj: PROPTYPE) -> None:
        self._check_type(obj)
        self._objs.insert(idx, obj)
        self._instance.property_changed(PropertyListInsert(self._name, idx, obj))

    def clear(self) -> None:
        while len(self._objs) > 0:
            self.__delitem__(0)

    def extend(self, value: Iterable[PROPTYPE]) -> None:
        for v in value:
            self.append(v)


class ListProperty(PropertyBase[SimpleObjectList[PROPTYPE]]):
    def __init__(self, t: Type[PROPTYPE]) -> None:
        super().__init__()
        assert isinstance(t, type)
        assert not isinstance(t, ObjectBase)
        self.type = t

    def get_value(self, instance: 'ObjectBase') -> SimpleObjectList[PROPTYPE]:
        value = super().get_value(instance)
        if value is None:
            value = SimpleObjectList(self.type, self.name, instance)
            instance.state[self.name] = value
        return value

    def set_value(self, instance: 'ObjectBase', value: SimpleObjectList[PROPTYPE]) -> None:
        raise RuntimeError("ListProperty cannot be assigned.")


OBJTYPE = TypeVar('OBJTYPE', bound='ObjectBase')
class ObjectProperty(PropertyBase[OBJTYPE]):
    def __init__(self, cls: Type[OBJTYPE]) -> None:
        super().__init__()
        assert isinstance(cls, type)
        self.cls = cls

    def set_value(self, instance: 'ObjectBase', value: OBJTYPE) -> None:
        if value is not None and not isinstance(value, self.cls):
            raise TypeError("Expected %s, got %s" % (self.cls.__name__, type(value).__name__))

        current = self.get_value(instance)
        if current is not None:
            if instance.attached_to_root:
                instance.root.remove_object(current)
            current.detach()
            current.clear_parent_container()

        if value is not None:
            value.attach(instance)
            value.set_parent_container(cast('ObjectList', self))  # why do I do this?
            if instance.attached_to_root:
                instance.root.add_object(value)

        super().set_value(instance, value)


class ObjectList(MutableSequence[OBJTYPE]):
    def __init__(self, name: str, instance: OBJTYPE) -> None:
        self._name = name
        self._instance = instance
        self._objs = []  # type: List['ObjectBase']

    def __len__(self) -> int:
        return len(self._objs)

    # pylint: disable=function-redefined,multiple-statements,pointless-statement
    @overload
    def __getitem__(self, idx: int) -> OBJTYPE:
        pass
    @overload
    def __getitem__(self, idx: slice) -> Sequence[OBJTYPE]:
        pass
    def __getitem__(self, idx: Union[int, slice]) -> Any:
        return self._objs[idx]

    @overload
    def __setitem__(self, idx: int, obj: OBJTYPE) -> None:
        pass
    @overload
    def __setitem__(self, idx: slice, obj: Iterable[OBJTYPE]) -> None:
        pass
    def __setitem__(self, idx: Union[int, slice], obj: Union[OBJTYPE, Iterable[OBJTYPE]]) -> None:
        if isinstance(idx, slice):
            idx = cast(slice, idx)
            obj = cast(Iterable[OBJTYPE], obj)
            for i, o in zip(range(idx.start, idx.stop, idx.step), obj):
                self.__delitem__(i)
                self.insert(i, o)
        elif isinstance(idx, int):
            idx = cast(int, idx)
            obj = cast(OBJTYPE, obj)
            self.__delitem__(idx)
            self.insert(idx, obj)
        else:
            raise TypeError(idx)

    @overload
    def __delitem__(self, idx: int) -> None:
        pass
    @overload
    def __delitem__(self, idx: slice) -> None:
        pass
    def __delitem__(self, idx: Union[int, slice]) -> None:
        if isinstance(idx, slice):
            raise NotImplementedError
        else:
            old_child = self._objs[idx]
            old_child.detach()
            old_child.clear_parent_container()
            if self._instance.attached_to_root:
                self._instance.root.remove_object(old_child)
            del self._objs[idx]
            for i in range(idx, len(self._objs)):
                self._objs[i].set_index(i)
            self._instance.property_changed(
                PropertyListDelete(self._name, idx, old_child))
    # pylint: enable=function-redefined,multiple-statements,pointless-statement

    def append(self, obj: OBJTYPE) -> None:
        self.insert(len(self._objs), obj)

    def insert(self, idx: int, obj: OBJTYPE) -> None:
        obj.attach(self._instance)
        obj.set_parent_container(self)
        if self._instance.attached_to_root:
            self._instance.root.add_object(obj)
        self._objs.insert(idx, obj)
        for i in range(idx, len(self._objs)):
            self._objs[i].set_index(i)
        self._instance.property_changed(
            PropertyListInsert(self._name, idx, obj))

    def clear(self) -> None:
        while len(self._objs) > 0:
            self.__delitem__(0)

    def extend(self, value: Iterable[OBJTYPE]) -> None:
        for v in value:
            self.append(v)


class ObjectListProperty(PropertyBase[ObjectList[OBJTYPE]]):
    def __init__(self, cls: Type[OBJTYPE]) -> None:
        super().__init__()
        assert isinstance(cls, type) and issubclass(cls, ObjectBase)
        self.cls = cls

    def get_value(self, instance: 'ObjectBase') -> ObjectList[OBJTYPE]:
        value = instance.state.get(self.name, None)
        if value is None:
            value = ObjectList(self.name, instance)
            instance.state[self.name] = value
        return value

    def set_value(self, instance: 'ObjectBase', value: ObjectList[OBJTYPE]) -> None:
        raise RuntimeError("ObjectListProperty cannot be assigned.")


class ObjectMeta(type):
    def __new__(mcs, name: str, parents: Any, dct: Dict[str, Any]) -> Any:
        for k, v in dct.items():
            if isinstance(v, PropertyBase):
                assert v.name is None
                v.name = k
        return super().__new__(mcs, name, parents, dct)


class ObjectBase(object, metaclass=ObjectMeta):
    id = Property(str, allow_none=False)

    def __init__(self) -> None:
        super().__init__()
        self.state = {}  # type: Dict[str, Any]
        self.parent = None  # type: ObjectBase
        self.__parent_container = None  # type: ObjectList
        self.__index = None  # type: int
        self.ref_count = 0

    def __str__(self) -> str:
        return '<%s id=%s>' % (type(self).__name__, self.id)
    __repr__ = __str__

    def __eq__(self, other: object) -> bool:
        if self.__class__ != other.__class__:
            return False
        other = cast(ObjectBase, other)
        if self.state != other.state:
            return False
        return True

    @property
    def is_root(self) -> bool:
        return False

    @property
    def root(self) -> 'RootObjectBase':
        if self.parent is None:
            if self.is_root:
                return cast(RootObjectBase, self)
            raise ObjectNotAttachedError(self)
        return self.parent.root

    @property
    def attached_to_root(self) -> bool:
        if self.parent is None:
            return self.is_root
        return self.parent.attached_to_root

    def attach(self, parent: 'ObjectBase') -> None:
        assert self.parent is None
        self.parent = parent

    def detach(self) -> None:
        assert self.parent is not None
        self.parent = None

    def is_child_of(self, parent: 'ObjectBase') -> bool:
        p = self.parent
        while p is not None:
            if p is parent:
                return True
            p = p.parent
        return False

    def set_parent_container(self, container: ObjectList) -> None:
        self.__parent_container = container

    def clear_parent_container(self) -> None:
        self.__parent_container = None
        self.__index = None

    def set_index(self, index: int) -> None:
        if self.__parent_container is None:
            raise ObjectNotAttachedError(self)
        self.__index = index

    @property
    def index(self) -> int:
        if self.__parent_container is None:
            raise ObjectNotAttachedError(self)
        assert self.__index is not None
        return self.__index

    @property
    def is_first(self) -> bool:
        if self.__index is None:
            raise NotListMemberError(self.id)
        return self.__index == 0

    @property
    def is_last(self) -> bool:
        if self.__index is None:
            raise NotListMemberError(self.id)
        return self.__index == len(self.__parent_container) - 1

    @property
    def prev_sibling(self) -> 'ObjectBase':
        if self.is_first:
            raise IndexError("First list member has no previous sibling.")
        return self.__parent_container[self.index - 1]

    @property
    def next_sibling(self) -> 'ObjectBase':
        if self.is_last:
            raise IndexError("Last list member has no next sibling.")
        return self.__parent_container[self.index + 1]

    def get_property(self, prop_name: str) -> PropertyBase:
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

    def list_properties(self) -> Iterator[PropertyBase]:
        for cls in self.__class__.__mro__:
            if not issubclass(cls, ObjectBase):
                continue
            for prop_name, prop in sorted(cls.__dict__.items()):
                if isinstance(prop, PropertyBase):
                    assert prop.name == prop_name
                    yield prop

    def list_property_names(self) -> Iterator[str]:
        for prop in self.list_properties():
            yield prop.name

    def property_changed(self, change: PropertyChange) -> None:
        print(change)

    def list_children(self) -> Iterator['ObjectBase']:
        for prop in self.list_properties():
            if isinstance(prop, ObjectProperty):
                obj = prop.get_value(self)
                if obj is not None:
                    yield obj
            elif isinstance(prop, ObjectListProperty):
                yield from prop.get_value(self)

    def walk_children(self, topdown: bool = True) -> Iterator['ObjectBase']:
        if topdown:
            yield self
        for child in self.list_children():
            yield from child.walk_children(topdown)
        if not topdown:
            yield self


class RootObjectBase(ObjectBase):
    @property
    def is_root(self) -> bool:
        return True

    def add_object(self, obj: ObjectBase) -> None:
        pass

    def remove_object(self, obj: ObjectBase) -> None:
        pass
