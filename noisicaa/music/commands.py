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

import logging
import time
import typing
from typing import Any, Dict, Tuple, Type

from google.protobuf import message as protobuf

from . import commands_pb2
from . import mutations
from . import pmodel

if typing.TYPE_CHECKING:
    from google.protobuf import descriptor as protobuf_descriptor

logger = logging.getLogger(__name__)


class ClientError(Exception):
    pass


class CommandRegistry(object):
    def __init__(self) -> None:
        self.__classes = {}  # type: Dict[str, Type[Command]]

    def register(self, cls: Type['Command']) -> None:
        assert cls.proto_type not in self.__classes
        self.__classes[cls.proto_type] = cls

    def create(self, proto: commands_pb2.Command, pool: pmodel.Pool) -> 'Command':
        assert proto.command in self.__classes, proto
        cls = self.__classes[proto.command]
        return cls(proto, pool)


class Command(object):
    proto_type = None  # type: str
    proto_ext = None  # type: protobuf_descriptor.FieldDescriptor

    def __init__(self, proto: commands_pb2.Command, pool: pmodel.Pool) -> None:
        self.__proto = proto
        self.pool = pool

    @property
    def pb(self) -> protobuf.Message:
        if self.proto_ext is not None:
            assert self.__proto.HasExtension(self.proto_ext), self.__proto
            return self.__proto.Extensions[self.proto_ext]
        else:
            assert self.__proto.HasField(self.proto_type), self.__proto
            return getattr(self.__proto, self.proto_type)

    def validate(self) -> None:
        pass

    def run(self) -> Any:
        raise NotImplementedError


class CommandSequence(object):
    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    # Instance members - must be set in create() and deserialize().
    proto = None  # type: commands_pb2.ExecutedCommand

    def __init__(self) -> None:
        raise RuntimeError(
            "Use CommandSequence.create() or CommandSequence.deserialize() to create instance.")

    def __str__(self) -> str:
        return str(self.proto)

    @property
    def command_names(self) -> str:
        parts = []

        name = None
        count = 0
        for cmd in self.proto.commands:
            if cmd.command == name:
                count += 1
                continue
            if name is not None:
                assert count > 0
                if count > 1:
                    parts.append('%d*%s' % (count, name))
                else:
                    parts.append(name)

            name = cmd.command
            count += 1

        if name is not None:
            assert count > 0
            if count > 1:
                parts.append('%d*%s' % (count, name))
            else:
                parts.append(name)

        return '[%s]' % ', '.join(parts)

    @classmethod
    def create(cls, proto: commands_pb2.CommandSequence) -> 'CommandSequence':
        cmd = cls.__new__(cls)
        cmd.proto = commands_pb2.ExecutedCommand(
            commands=proto.commands,
            status=commands_pb2.ExecutedCommand.NOT_APPLIED,
            create_timestamp=int(time.time()),
            version=cls.VERSION,
        )
        return cmd

    @classmethod
    def deserialize(cls, data: bytes) -> 'CommandSequence':
        cmd_proto = commands_pb2.ExecutedCommand()
        cmd_proto.MergeFromString(data)

        if cmd_proto.version not in cls.SUPPORTED_VERSIONS:
            raise ValueError("Version %s not supported." % cmd_proto.version)

        cmd = cls.__new__(cls)
        cmd.proto = cmd_proto
        return cmd

    def serialize(self) -> bytes:
        return self.proto.SerializeToString()

    @property
    def is_noop(self) -> bool:
        return len(self.proto.log.ops) == 0

    def try_merge_with(self, other: 'CommandSequence') -> bool:
        k = None  # type: Tuple[Any, ...]

        property_changes_a = {}  # type: Dict[Tuple[Any, ...], int]
        for op in self.proto.log.ops:
            if op.WhichOneof('op') == 'set_property':
                k = (op.set_property.obj_id, op.set_property.prop_name)
                property_changes_a[k] = op.set_property.new_slot
            elif op.WhichOneof('op') == 'list_set':
                k = (op.list_set.obj_id, op.list_set.prop_name, op.list_set.index)
                property_changes_a[k] = op.list_set.new_slot
            else:
                return False

        property_changes_b = {}  # type: Dict[Tuple[Any, ...], int]
        for op in other.proto.log.ops:
            if op.WhichOneof('op') == 'set_property':
                k = (op.set_property.obj_id, op.set_property.prop_name)
                property_changes_b[k] = op.set_property.new_slot
            elif op.WhichOneof('op') == 'list_set':
                k = (op.list_set.obj_id, op.list_set.prop_name, op.list_set.index)
                property_changes_b[k] = op.list_set.new_slot
            else:
                return False

        if set(property_changes_a.keys()) != set(property_changes_b.keys()):
            return False

        self.proto.commands.extend(other.proto.commands)
        for k, slot_idx_a in property_changes_b.items():
            slot_a = self.proto.log.slots[slot_idx_a]
            slot_b = other.proto.log.slots[property_changes_b[k]]
            assert slot_a.WhichOneof('value') == slot_b.WhichOneof('value'), (slot_a, slot_b)
            self.proto.log.slots[slot_idx_a].CopyFrom(slot_b)

        return True

    @property
    def num_log_ops(self) -> int:
        return len(self.proto.log.ops)

    def apply(self, registry: CommandRegistry, pool: pmodel.Pool) -> Any:
        assert self.proto.status == commands_pb2.ExecutedCommand.NOT_APPLIED

        results = []

        collector = mutations.MutationCollector(pool, self.proto.log)
        with collector.collect():
            try:
                commands = [registry.create(cmd_proto, pool) for cmd_proto in self.proto.commands]

                try:
                    for cmd in commands:
                        cmd.validate()

                except Exception as exc:
                    raise ClientError(exc)

                for cmd in commands:
                    results.append(cmd.run())

            except:
                self.proto.status = commands_pb2.ExecutedCommand.FAILED
                raise

        self.proto.status = commands_pb2.ExecutedCommand.APPLIED
        return results

    def redo(self, pool: pmodel.Pool) -> None:
        assert self.proto.status == commands_pb2.ExecutedCommand.APPLIED

        mutation_list = mutations.MutationList(pool, self.proto.log)
        mutation_list.apply_forward()

    def undo(self, pool: pmodel.Pool) -> None:
        assert self.proto.status == commands_pb2.ExecutedCommand.APPLIED

        mutation_list = mutations.MutationList(pool, self.proto.log)
        mutation_list.apply_backward()
