#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import copy
import random
import sys
import typing
from typing import (
    cast, overload,
    Any, Optional, Union,
    Iterable, Iterator, MutableMapping, Sequence, MutableSequence, Dict, Type, Generic, TypeVar)

from google.protobuf import message as protobuf
from google.protobuf.internal import containers as protobuf_containers

from . import model_base_pb2

if typing.TYPE_CHECKING:
    from google.protobuf import descriptor as protobuf_descriptor


def _checktype(o: Any, t: Type) -> None:
    if not isinstance(o, t):
        raise TypeError("Expected %s, got %s" % (t.__name__, type(o).__name__))


VALUE = TypeVar('VALUE')
PROTO = TypeVar('PROTO', bound=protobuf.Message)
PROTOVAL = TypeVar('PROTOVAL', bound='ProtoValue')
OBJECT = TypeVar('OBJECT', bound='ObjectBase')
POOLOBJECTBASE = TypeVar('POOLOBJECTBASE', bound='ObjectBase')


class AbstractPool(Generic[POOLOBJECTBASE], MutableMapping[int, POOLOBJECTBASE]):
    def register_class(self, cls: Type[POOLOBJECTBASE]) -> None:
        raise NotImplementedError  # pragma: no coverage

    def set_root(self, obj: POOLOBJECTBASE) -> None:
        raise NotImplementedError  # pragma: no coverage

    @property
    def root(self) -> POOLOBJECTBASE:
        raise NotImplementedError  # pragma: no coverage

    @property
    def objects(self) -> Iterator[POOLOBJECTBASE]:
        raise NotImplementedError  # pragma: no coverage

    def create(  # pylint: disable=redefined-builtin
            self, cls: Type[OBJECT], id: Optional[int] = None, **kwargs: Any) -> OBJECT:
        raise NotImplementedError  # pragma: no coverage

    def deserialize(self, pb: model_base_pb2.ObjectBase) -> POOLOBJECTBASE:
        raise NotImplementedError  # pragma: no coverage


class ValueNotSetError(ValueError):
    pass

class ObjectNotAttachedError(ValueError):
    def __init__(self, obj: 'ObjectBase') -> None:
        super().__init__(str(obj))

class NotListMemberError(ValueError):
    pass

class InvalidReferenceError(ValueError):
    pass


class Mutation(object):
    def _fmt(self, **kwargs: Any) -> str:
        return '<%s%s>' % (
            type(self).__name__, ''.join(' %s=%r' % (k, v) for k, v in sorted(kwargs.items())))


class ObjectChange(Mutation):
    def __init__(self, obj: 'ObjectBase') -> None:
        self.obj = obj

    def __str__(self) -> str:
        return self._fmt(id=self.obj.id)


class ObjectAdded(ObjectChange):
    pass


class ObjectRemoved(ObjectChange):
    pass


class PropertyChange(Generic[VALUE], Mutation):
    def __init__(self, obj: 'ObjectBase', prop_name: str) -> None:
        self.obj = obj
        self.prop_name = prop_name


class PropertyValueChange(Generic[VALUE], PropertyChange[VALUE]):
    def __init__(
            self, obj: 'ObjectBase', prop_name: str, old_value: VALUE, new_value: VALUE) -> None:
        super().__init__(obj, prop_name)
        self.old_value = old_value
        self.new_value = new_value

    def __str__(self) -> str:
        return self._fmt(old=self.old_value, new=self.new_value)


class PropertyListChange(Generic[VALUE], PropertyChange[VALUE]):
    pass


class PropertyListInsert(Generic[VALUE], PropertyListChange[VALUE]):
    def __init__(self, obj: 'ObjectBase', prop_name: str, index: int, new_value: VALUE) -> None:
        super().__init__(obj, prop_name)
        self.index = index
        self.new_value = new_value

    def __str__(self) -> str:
        return self._fmt(index=self.index, new=self.new_value)


class PropertyListDelete(Generic[VALUE], PropertyListChange[VALUE]):
    def __init__(self, obj: 'ObjectBase', prop_name: str, index: int, old_value: VALUE) -> None:
        super().__init__(obj, prop_name)
        self.index = index
        self.old_value = old_value

    def __str__(self) -> str:
        return self._fmt(index=self.index, old=self.old_value)


# TODO: use a protocol instead of a base class
#   Then I can use MusicalTime without hassle
class ProtoValue(object):
    def to_proto(self) -> protobuf.Message:
        raise NotImplementedError  # pragma: no coverage

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'ProtoValue':
        raise NotImplementedError  # pragma: no coverage


class BaseList(Generic[VALUE], MutableSequence[VALUE]):
    def __init__(
            self, instance: 'ObjectBase', prop_name: str, pb: protobuf_containers.BaseContainer
    ) -> None:
        self._instance = instance
        self._prop_name = prop_name
        self._pb = pb

    def __repr__(self) -> str:
        return '[%s]' % ', '.join(repr(v) for v in self)

    def __eq__(self, other: object) -> bool:
        if not issubclass(type(other), Sequence):
            raise TypeError
        other = cast(Sequence, other)
        if len(self) != len(other):
            return False
        for v1, v2 in zip(self, other):
            if v1 != v2:
                return False
        return True

    def __len__(self) -> int:
        return len(self._pb)

    def append(self, obj: VALUE) -> None:
        self.insert(len(self._pb), obj)

    def extend(self, objs: Iterable[VALUE]) -> None:
        for obj in objs:
            self.append(obj)

    def clear(self) -> None:
        for idx in range(len(self._pb) - 1, -1, -1):
            self.delete(idx)

    def __iter__(self) -> Iterator[VALUE]:
        for idx in range(len(self._pb)):
            yield self.get(idx)

    def __range(self, s: slice) -> Iterator[int]:
        start = s.start if s.start is not None else 0
        if start < 0:
            start = len(self._pb) + start
        stop = s.stop if s.stop is not None else len(self._pb)
        if stop < 0:
            stop = len(self._pb) + stop
        step = s.step if s.step is not None else 1
        yield from range(start, stop, step)

    # pylint: disable=function-redefined
    @overload
    def __getitem__(self, idx: int) -> VALUE:
        pass  # pragma: no coverage
    @overload
    def __getitem__(self, idx: slice) -> MutableSequence[VALUE]:
        pass  # pragma: no coverage
    def __getitem__(self, idx: Union[int, slice]) -> Any:
        if isinstance(idx, int):
            if idx < 0:
                idx = len(self._pb) + idx
            if not 0 <= idx < len(self._pb):
                raise IndexError("Index %d out of range (%d)" % (idx, len(self._pb)))
            return self.get(idx)
        else:
            return [self.get(i) for i in self.__range(idx)]

    @overload
    def __setitem__(self, idx: int, value: VALUE) -> None:
        pass  # pragma: no coverage
    @overload
    def __setitem__(self, idx: slice, value: Iterable[VALUE]) -> None:
        pass  # pragma: no coverage
    def __setitem__(self, idx: Union[int, slice], value: Union[VALUE, Iterable[VALUE]]) -> None:
        if isinstance(idx, int):
            self.delete(idx)
            self.insert(idx, cast(VALUE, value))
        else:
            for i, v in zip(self.__range(idx), cast(Iterable[VALUE], value)):
                self.delete(i)
                self.insert(i, v)

    @overload
    def __delitem__(self, idx: int) -> None:
        pass  # pragma: no coverage
    @overload
    def __delitem__(self, idx: slice) -> None:
        pass  # pragma: no coverage
    def __delitem__(self, idx: Union[int, slice]) -> None:
        if isinstance(idx, int):
            self.delete(idx)
        else:
            raise NotImplementedError  # pragma: no coverage
    # pylint: enable=function-redefined

    def get(self, idx: int) -> VALUE:
        raise NotImplementedError(type(self).__name__)  # pragma: no coverage

    def insert(self, idx: int, obj: VALUE) -> None:
        raise NotImplementedError(type(self).__name__)  # pragma: no coverage

    def delete(self, idx: int) -> None:
        raise NotImplementedError(type(self).__name__)  # pragma: no coverage


class SimpleList(Generic[VALUE], BaseList[VALUE]):
    _pb = None  # type: protobuf_containers.RepeatedScalarFieldContainer

    def __init__(
            self, instance: 'ObjectBase', prop_name: str,
            pb: protobuf_containers.RepeatedScalarFieldContainer, ptype: Type[VALUE]
    ) -> None:
        super().__init__(instance, prop_name, pb)
        self.__ptype = ptype

    def get(self, idx: int) -> VALUE:
        return self._pb[idx]

    def insert(self, idx: int, value: VALUE) -> None:
        if idx < 0 or idx > len(self._pb):
            raise IndexError("Index %d out of bounds [0:%d]" % (idx, len(self._pb)))

        self._pb.insert(idx, value)
        if not self._instance.in_setup:
            self._instance.property_changed(PropertyListInsert(
                self._instance, self._prop_name, idx, value))

    def delete(self, idx: int) -> None:
        old_value = self._pb[idx]
        del self._pb[idx]
        if not self._instance.in_setup:
            self._instance.property_changed(PropertyListDelete(
                self._instance, self._prop_name, idx, old_value))


class WrappedProtoList(BaseList[PROTOVAL]):
    _pb = None  # type: protobuf_containers.RepeatedCompositeFieldContainer

    def __init__(
            self, instance: 'ObjectBase', prop_name: str,
            pb: protobuf_containers.RepeatedCompositeFieldContainer,
            ptype: Type[PROTOVAL]) -> None:
        super().__init__(instance, prop_name, pb)
        self.__ptype = ptype

    def get(self, idx: int) -> PROTOVAL:
        return cast(PROTOVAL, self.__ptype.from_proto(self._pb[idx]))

    def insert(self, idx: int, value: PROTOVAL) -> None:
        _checktype(value, self.__ptype)
        if idx < 0 or idx > len(self._pb):
            raise IndexError("Index %d out of bounds [0:%d]" % (idx, len(self._pb)))

        self._pb.add()
        for m in range(len(self._pb) - 1, idx, -1):
            self._pb[m].CopyFrom(self._pb[m - 1])
        self._pb[idx].CopyFrom(value.to_proto())
        if not self._instance.in_setup:
            self._instance.property_changed(
                PropertyListInsert(self._instance, self._prop_name, idx, value))

    def delete(self, idx: int) -> None:
        old_value = self.__ptype.from_proto(self._pb[idx])
        del self._pb[idx]
        if not self._instance.in_setup:
            self._instance.property_changed(
                PropertyListDelete(self._instance, self._prop_name, idx, old_value))


class ObjectList(Generic[OBJECT], BaseList[OBJECT]):
    _pb = None  # type: protobuf_containers.RepeatedScalarFieldContainer

    def __init__(
            self, instance: 'ObjectBase', prop_name: str,
            pb: protobuf_containers.RepeatedScalarFieldContainer,
            otype: Type[OBJECT], pool: AbstractPool) -> None:
        super().__init__(instance, prop_name, pb)
        self.__otype = otype
        self.__pool = pool

    def get(self, idx: int) -> OBJECT:
        obj_id = self._pb[idx]
        try:
            return cast(OBJECT, self.__pool[obj_id])
        except KeyError:
            raise InvalidReferenceError(
                "%s.%s[%s]" % (type(self._instance).__name__, self._prop_name, idx))

    def insert(self, idx: int, obj: OBJECT) -> None:
        _checktype(obj, self.__otype)
        if idx < 0 or idx > len(self._pb):
            raise IndexError("Index %d out of bounds [0:%d]" % (idx, len(self._pb)))

        obj.attach(self._instance)
        obj.set_parent_container(self)
        self._pb.insert(idx, obj.id)
        for i in range(idx, len(self._pb)):
            self.__pool[self._pb[i]].set_index(i)
        if not self._instance.in_setup:
            self._instance.property_changed(
                PropertyListInsert(self._instance, self._prop_name, idx, obj))

    def delete(self, idx: int) -> None:
        old_child = self.__pool[self._pb[idx]]
        old_child.detach()
        old_child.clear_parent_container()
        del self._pb[idx]
        for i in range(idx, len(self._pb)):
            self.__pool[self._pb[i]].set_index(i)
        if not self._instance.in_setup:
            self._instance.property_changed(
                PropertyListDelete(self._instance, self._prop_name, idx, old_child))


class PropertyBase(object):
    def __init__(self) -> None:
        self.name = None  # type: str
        self.spec = None  # type: ObjectSpec

    def get_value(self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool) -> Any:
        raise NotImplementedError(type(self).__name__)  # pragma: no coverage

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: Any
    ) -> None:
        raise NotImplementedError(type(self).__name__)  # pragma: no coverage


class Property(Generic[VALUE], PropertyBase):
    def __init__(
            self, ptype: Type[VALUE], *, allow_none: bool = False, default: Optional[VALUE] = None
    ) -> None:
        super().__init__()
        self.ptype = ptype
        self.allow_none = allow_none
        self.default = default

    def get_value(self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool) -> VALUE:
        if pb.HasField(self.name):
            return getattr(pb, self.name)
        if self.default is not None:
            return self.default
        if self.allow_none:
            return None
        raise ValueNotSetError("Value '%s' has not been set." % self.name)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: VALUE
    ) -> None:
        if pb.HasField(self.name):
            old_value = getattr(pb, self.name)
        else:
            old_value = self.default

        if value is None:
            if self.allow_none:
                pb.ClearField(self.name)
            else:
                raise ValueError("None not allowed for '%s'." % self.name)
        else:
            setattr(pb, self.name, value)

        if value != old_value and not instance.in_setup:
            instance.property_changed(PropertyValueChange(instance, self.name, old_value, value))


class ProtoProperty(Generic[PROTO], PropertyBase):
    def __init__(
            self, ptype: Type[PROTO], *, allow_none: bool = False,
            default: Optional[PROTO] = None
    ) -> None:
        super().__init__()
        self.ptype = ptype
        self.allow_none = allow_none
        self.default = default

    def get_value(self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool) -> PROTO:
        if pb.HasField(self.name):
            return getattr(pb, self.name)
        if self.default is not None:
            return self.default
        if self.allow_none:
            return None
        raise ValueNotSetError("Value '%s' has not been set." % self.name)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: PROTO
    ) -> None:
        if pb.HasField(self.name):
            old_value = copy.deepcopy(getattr(pb, self.name))
        else:
            old_value = self.default

        if value is None:
            if self.allow_none:
                pb.ClearField(self.name)
            else:
                raise ValueError("None not allowed for '%s'." % self.name)
        else:
            _checktype(value, self.ptype)
            getattr(pb, self.name).CopyFrom(value)

        if value != old_value and not instance.in_setup:
            instance.property_changed(PropertyValueChange(instance, self.name, old_value, value))


class WrappedProtoProperty(Generic[PROTOVAL], PropertyBase):
    def __init__(
            self, ptype: Type[PROTOVAL], *, allow_none: bool = False,
            default: Optional[PROTOVAL] = None
    ) -> None:
        super().__init__()
        self.ptype = ptype
        self.allow_none = allow_none
        self.default = default

    def get_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool) -> PROTOVAL:
        if pb.HasField(self.name):
            return cast(PROTOVAL, self.ptype.from_proto(getattr(pb, self.name)))
        if self.default is not None:
            return self.default
        if self.allow_none:
            return None
        raise ValueNotSetError("Value '%s' has not been set." % self.name)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: PROTOVAL
    ) -> None:
        if pb.HasField(self.name):
            old_value = self.ptype.from_proto(getattr(pb, self.name))
        else:
            old_value = self.default

        if value is None:
            if self.allow_none:
                pb.ClearField(self.name)
            else:
                raise ValueError("None not allowed for '%s'." % self.name)
        else:
            _checktype(value, self.ptype)
            getattr(pb, self.name).CopyFrom(value.to_proto())

        if value != old_value and not instance.in_setup:
            instance.property_changed(PropertyValueChange(instance, self.name, old_value, value))


class ListProperty(Generic[VALUE], PropertyBase):
    def __init__(self, ptype: Type[VALUE]) -> None:
        super().__init__()
        self.ptype = ptype

    def get_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool
    ) -> MutableSequence[VALUE]:
        return SimpleList[VALUE](instance, self.name, getattr(pb, self.name), self.ptype)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: VALUE
    ) -> None:
        raise TypeError("%s cannot be assigned." % self.name)


class WrappedProtoListProperty(Generic[PROTOVAL], PropertyBase):
    def __init__(self, ptype: Type[PROTOVAL]) -> None:
        super().__init__()
        self.ptype = ptype

    def get_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool
    ) -> MutableSequence[PROTOVAL]:
        return WrappedProtoList[PROTOVAL](instance, self.name, getattr(pb, self.name), self.ptype)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: PROTOVAL
    ) -> None:
        raise TypeError("%s cannot be assigned." % self.name)


class ObjectProperty(Generic[OBJECT], PropertyBase):
    def __init__(self, otype: Type[OBJECT], *, allow_none: bool = False) -> None:
        super().__init__()
        self.otype = otype
        self.allow_none = allow_none

    def get_value(self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool) -> OBJECT:
        if pb.HasField(self.name):
            obj_id = getattr(pb, self.name)
            try:
                return cast(OBJECT, pool[obj_id])
            except KeyError:
                raise InvalidReferenceError("%s.%s" % (type(instance).__name__, self.name))
        if self.allow_none:
            return None
        raise ValueNotSetError("Value '%s' has not been set." % self.name)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: OBJECT
    ) -> None:
        if value is not None:
            _checktype(value, self.otype)
        elif not self.allow_none:
            raise ValueError("None not allowed for '%s'." % self.name)

        if pb.HasField(self.name):
            old_id = getattr(pb, self.name)
        else:
            old_id = None
        new_id = value.id if value is not None else None
        if new_id == old_id:
            return

        old_value = pool[old_id] if old_id is not None else None

        if old_value is not None:
            old_value.detach()

        if value is None:
            pb.ClearField(self.name)
        else:
            value.attach(instance)
            setattr(pb, self.name, value.id)

        if not instance.in_setup:
            instance.property_changed(PropertyValueChange(instance, self.name, old_value, value))


class ObjectReferenceProperty(Generic[OBJECT], PropertyBase):
    def __init__(self, otype: Type[OBJECT], *, allow_none: bool = False) -> None:
        super().__init__()
        self.otype = otype
        self.allow_none = allow_none

    def get_value(self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool) -> OBJECT:
        if pb.HasField(self.name):
            obj_id = getattr(pb, self.name)
            try:
                return cast(OBJECT, pool[obj_id])
            except KeyError:
                raise InvalidReferenceError("%s.%s" % (type(instance).__name__, self.name))
        if self.allow_none:
            return None
        raise ValueNotSetError("Value '%s' has not been set." % self.name)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: OBJECT
    ) -> None:
        if value is not None:
            _checktype(value, self.otype)
        elif not self.allow_none:
            raise ValueError("None not allowed for '%s'." % self.name)

        if pb.HasField(self.name):
            old_id = getattr(pb, self.name)
        else:
            old_id = None
        new_id = value.id if value is not None else None
        if new_id == old_id:
            return

        old_value = pool[old_id] if old_id is not None else None

        if value is None:
            pb.ClearField(self.name)
        else:
            setattr(pb, self.name, value.id)

        if not instance.in_setup:
            instance.property_changed(PropertyValueChange(instance, self.name, old_value, value))


class ObjectListProperty(Generic[OBJECT], PropertyBase):
    def __init__(self, otype: Type[OBJECT]) -> None:
        super().__init__()
        self.otype = otype

    def get_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool
    ) -> MutableSequence[OBJECT]:
        return ObjectList(instance, self.name, getattr(pb, self.name), self.otype, pool)

    def set_value(
            self, instance: 'ObjectBase', pb: protobuf.Message, pool: AbstractPool, value: OBJECT
    ) -> None:
        raise TypeError("%s cannot be assigned." % self.name)


class ObjectSpecMeta(type):
    def __new__(mcs, name: str, parents: Any, dct: Dict[str, Any]) -> Any:
        spec = cast('ObjectSpec', super().__new__(mcs, name, parents, dct))
        for name, attr in dct.items():
            if isinstance(attr, PropertyBase):
                assert attr.name is None
                attr.name = name
                attr.spec = spec
        return spec


class ObjectSpec(object, metaclass=ObjectSpecMeta):
    proto_type = None  # type: str
    proto_ext = None  # type: protobuf_descriptor.FieldDescriptor


class ObjectBase(object):
    # Do not complain about 'id' arguments.
    # pylint: disable=redefined-builtin

    class ObjectBaseSpec(ObjectSpec):
        id = Property(int)

    @classmethod
    def get_spec(cls) -> Type[ObjectSpec]:
        for spec in cls.__dict__.values():
            if isinstance(spec, type) and issubclass(spec, ObjectSpec):
                return spec

        return None

    def __init__(self, *, pb: model_base_pb2.ObjectBase, pool: AbstractPool) -> None:
        self.__proto = pb
        self._pool = pool

        self.__properties = {}  # type: Dict[str, PropertyBase]
        for cls in self.__class__.__mro__:
            if not issubclass(cls, ObjectBase):
                continue  # pragma: no coverage

            spec = cast(Type[ObjectBase], cls).get_spec()
            if spec is None:
                continue

            for prop_name, prop in spec.__dict__.items():
                if isinstance(prop, PropertyBase):
                    self.__properties[prop_name] = prop

        self.__parent = None  # type: ObjectBase
        self.__parent_container = None  # type: ObjectList
        self.__index = None  # type: int
        self.in_setup = True

    def create(self, **kwargs: Any) -> None:
        assert not kwargs, kwargs

    def setup(self) -> None:
        pass

    def setup_complete(self) -> None:
        self.in_setup = False

    @property
    def proto(self) -> model_base_pb2.ObjectBase:
        return self.__proto

    def get_property_value(self, prop_name: str) -> Any:
        prop = self.__properties[prop_name]
        return prop.get_value(self, self.__proto.Extensions[prop.spec.proto_ext], self._pool)

    def set_property_value(self, prop_name: str, value: Any) -> None:
        prop = self.__properties[prop_name]
        prop.set_value(self, self.__proto.Extensions[prop.spec.proto_ext], self._pool, value)

    @property
    def id(self) -> int:
        return ObjectBase.ObjectBaseSpec.id.get_value(self, self.__proto, self._pool)

    def __str__(self) -> str:
        return '<%s id=%s>' % (type(self).__name__, self.id)
    __repr__ = __str__

    def __eq__(self, other: object) -> bool:
        if self.__class__ != other.__class__:
            return False
        other = cast(ObjectBase, other)
        return self.proto == other.proto

    @property
    def parent(self) -> Optional['ObjectBase']:
        return self.__parent

    @property
    def is_attached(self) -> bool:
        return self.__parent is not None

    def attach(self, parent: 'ObjectBase') -> None:
        assert self.__parent is None
        self.__parent = parent

    def detach(self) -> None:
        assert self.__parent is not None
        self.__parent = None

    def is_child_of(self, parent: 'ObjectBase') -> bool:
        p = self.__parent
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
        assert self.__parent_container is not None
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
        try:
            return self.__properties[prop_name]
        except KeyError:
            raise AttributeError("%s has not property %s" % (self.__class__.__name__, prop_name))

    def list_properties(self) -> Iterator[PropertyBase]:
        for _, prop in sorted(self.__properties.items()):
            yield prop

    def list_property_names(self) -> Iterator[str]:
        for prop in self.list_properties():
            yield prop.name

    def property_changed(self, change: PropertyChange) -> None:
        pass  # pragma: no coverage

    def list_children(self) -> Iterator['ObjectBase']:
        for prop in self.list_properties():
            if isinstance(prop, ObjectProperty):
                try:
                    obj = getattr(self, prop.name)
                except ValueNotSetError:
                    obj = None
                if obj is not None:
                    yield obj
            elif isinstance(prop, ObjectListProperty):
                yield from getattr(self, prop.name)

    def walk_object_tree(self) -> Iterator['ObjectBase']:
        for child in self.list_children():
            yield from child.walk_object_tree()

        yield self

    def serialize(self) -> model_base_pb2.ObjectTree:
        objtree = model_base_pb2.ObjectTree()
        objtree.root = self.id
        for obj in self.walk_object_tree():
            oproto = objtree.objects.add()
            oproto.CopyFrom(obj.proto)

        return objtree

    def reset_state(self) -> None:
        for prop in self.list_properties():
            if isinstance(prop, ObjectProperty):
                try:
                    child = self.get_property_value(prop.name)
                except ValueNotSetError:
                    child = None
                if child is not None:
                    child.detach()
            elif isinstance(prop, ObjectListProperty):
                children = self.get_property_value(prop.name)
                for child in children:
                    child.detach()
                    child.clear_parent_container()

        self.__proto = model_base_pb2.ObjectBase(
            id=self.__proto.id,
            type=self.__proto.type)


class Pool(Generic[POOLOBJECTBASE], AbstractPool[POOLOBJECTBASE]):
    # Do not complain about redefining builtin name 'id'
    # pylint: disable=redefined-builtin

    def __init__(self) -> None:
        super().__init__()

        self.__obj_map = {}  # type: Dict[int, POOLOBJECTBASE]
        self.__class_map = {}  # type: Dict[str, Type[POOLOBJECTBASE]]
        self.__root_obj = None  # type: POOLOBJECTBASE

    def __get_proto_type(self, cls: Type) -> str:
        proto_type = None
        for c in cls.__mro__:
            if not issubclass(c, ObjectBase):
                continue  # pragma: no coverage

            spec = cast(Type[ObjectBase], c).get_spec()
            if spec is None:
                continue

            if spec.proto_type is not None:
                assert proto_type is None, (cls.__name__, c.__name__)
                proto_type = spec.proto_type

        return proto_type

    def register_class(self, cls: Type[POOLOBJECTBASE]) -> None:
        proto_type = self.__get_proto_type(cls)
        assert proto_type is not None, cls.__name__
        assert proto_type not in self.__class_map
        self.__class_map[proto_type] = cls

    def set_root(self, obj: POOLOBJECTBASE) -> None:
        assert self.__root_obj is None
        self.__root_obj = obj

    @property
    def root(self) -> POOLOBJECTBASE:
        assert self.__root_obj is not None
        return self.__root_obj

    def object_added(self, obj: POOLOBJECTBASE) -> None:
        pass

    def object_removed(self, obj: POOLOBJECTBASE) -> None:
        pass

    def __getitem__(self, id: int) -> POOLOBJECTBASE:
        try:
            return self.__obj_map[id]
        except KeyError:
            raise KeyError("%016x" % id).with_traceback(sys.exc_info()[2]) from None

    def __setitem__(self, id: int, obj: POOLOBJECTBASE) -> None:
        raise RuntimeError("Not allowed.")

    def __delitem__(self, id: int) -> None:
        self.delete(id)

    def __len__(self) -> int:
        return len(self.__obj_map)

    def __iter__(self) -> Iterator[int]:
        yield from self.__obj_map

    @property
    def objects(self) -> Iterator[POOLOBJECTBASE]:
        yield from self.__obj_map.values()

    def __attach_children(self, obj: ObjectBase) -> None:
        for prop in obj.list_properties():
            if isinstance(prop, ObjectProperty):
                try:
                    child = obj.get_property_value(prop.name)
                except ValueNotSetError:
                    child = None
                if child is not None:
                    child.attach(obj)
            elif isinstance(prop, ObjectListProperty):
                children = obj.get_property_value(prop.name)
                for idx, child in enumerate(children):
                    child.attach(obj)
                    child.set_parent_container(children)
                    child.set_index(idx)

    def create(
            self, cls: Type[OBJECT], id: Optional[int] = None, **kwargs: Any) -> OBJECT:
        proto_type = self.__get_proto_type(cls)
        assert proto_type in self.__class_map, cls.__name__
        if id is None:
            id = random.getrandbits(64)
        pb = model_base_pb2.ObjectBase(id=id, type=proto_type)
        obj = cast(POOLOBJECTBASE, cls(pb=pb, pool=self))
        self.__obj_map[id] = obj
        obj.create(**kwargs)  # type: ignore
        obj.setup()
        obj.setup_complete()
        self.object_added(obj)
        return cast(OBJECT, obj)

    def deserialize(self, pb: model_base_pb2.ObjectBase) -> POOLOBJECTBASE:
        assert pb.id not in self.__obj_map, str(pb)
        cls = self.__class_map[pb.type]
        obj = cls(pb=pb, pool=self)
        self.__obj_map[pb.id] = obj

        self.__attach_children(obj)
        obj.setup()
        obj.setup_complete()
        self.object_added(obj)
        return obj

    def remove(self, id: int) -> None:
        obj = self.__obj_map[id]
        del self.__obj_map[id]
        self.object_removed(obj)

    def delete(self, id: int) -> None:
        obj = self.__obj_map[id]
        for child in obj.list_children():
            self.delete(child.id)
        del self.__obj_map[id]
        self.object_removed(obj)

    def deserialize_tree(self, objtree: model_base_pb2.ObjectTree) -> POOLOBJECTBASE:
        for oproto in objtree.objects:
            self.deserialize(oproto)
        self.set_root(self.__obj_map[objtree.root])
        return self.__obj_map[objtree.root]

    def clone_tree(self, objtree: model_base_pb2.ObjectTree) -> POOLOBJECTBASE:
        idmap = {}  # type: Dict[int, int]
        for oproto in objtree.objects:
            idmap[oproto.id] = random.getrandbits(64)

        for oproto in objtree.objects:
            oproto = copy.deepcopy(oproto)
            oproto.id = idmap[oproto.id]

            cls = self.__class_map[oproto.type]
            obj = cast(POOLOBJECTBASE, cls(pb=oproto, pool=self))
            self.__obj_map[oproto.id] = obj

            # Rewrite all IDs directly in the proto.
            for prop in obj.list_properties():
                try:
                    ext = oproto.Extensions[prop.spec.proto_ext]
                except KeyError:
                    continue

                if isinstance(prop, ObjectProperty):
                    if ext.HasField(prop.name):
                        child_id = getattr(ext, prop.name)
                        child_id = idmap[child_id]
                        setattr(ext, prop.name, child_id)

                elif isinstance(prop, ObjectListProperty):
                    old_ids = list(getattr(ext, prop.name))
                    ext.ClearField(prop.name)
                    lst = getattr(ext, prop.name)
                    for child_id in old_ids:
                        child_id = idmap[child_id]
                        lst.append(child_id)

                elif isinstance(prop, ObjectReferenceProperty):
                    if ext.HasField(prop.name):
                        child_id = getattr(ext, prop.name)
                        if child_id in idmap:
                            setattr(ext, prop.name, idmap[child_id])

            self.__attach_children(obj)
            obj.setup()
            obj.setup_complete()
            self.object_added(obj)

        return self.__obj_map[idmap[objtree.root]]
