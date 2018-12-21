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
import time
from typing import Any, Dict, Type

from google.protobuf import message as protobuf

from . import commands_pb2
from . import mutations
from . import pmodel

logger = logging.getLogger(__name__)


class Command(object):
    proto_type = None  # type: str
    command_classes = {}  # type: Dict[str, Type[Command]]

    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    # Instance members - must be set in create() and deserialize().
    proto = None  # type: commands_pb2.ExecutedCommand

    def __init__(self) -> None:
        raise RuntimeError("Use Command.create() or Command.deserialize() to create instance.")

    def __str__(self) -> str:
        return str(self.proto)

    @classmethod
    def register_command(cls, cmd_cls: Type['Command']) -> None:
        assert cmd_cls.proto_type not in cls.command_classes
        cls.command_classes[cmd_cls.proto_type] = cmd_cls

    @classmethod
    def create(cls, proto: commands_pb2.Command) -> 'Command':
        proto_type = proto.WhichOneof('command')
        assert proto_type in cls.command_classes, proto_type
        cmd_cls = cls.command_classes[proto_type]
        cmd = cmd_cls.__new__(cmd_cls)
        cmd.proto = commands_pb2.ExecutedCommand(
            command=proto,
            status=commands_pb2.ExecutedCommand.NOT_APPLIED,
            create_timestamp=int(time.time()),
            version=cls.VERSION,
        )
        return cmd

    @classmethod
    def deserialize(cls, data: bytes) -> 'Command':
        cmd_proto = commands_pb2.ExecutedCommand()
        cmd_proto.MergeFromString(data)

        if cmd_proto.version not in cls.SUPPORTED_VERSIONS:
            raise ValueError("Version %s not supported." % cmd_proto.version)

        proto_type = cmd_proto.command.WhichOneof('command')
        assert proto_type in cls.command_classes, proto_type
        cmd_cls = cls.command_classes[proto_type]
        cmd = cmd_cls.__new__(cmd_cls)
        cmd.proto = cmd_proto
        return cmd

    def serialize(self) -> bytes:
        return self.proto.SerializeToString()

    @property
    def is_noop(self) -> bool:
        return len(self.proto.log.ops) == 0

    @property
    def num_log_ops(self) -> int:
        return len(self.proto.log.ops)

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> Any:
        raise NotImplementedError

    def apply(self, project: pmodel.Project, pool: pmodel.Pool) -> Any:
        assert self.proto.status == commands_pb2.ExecutedCommand.NOT_APPLIED

        assert self.proto.command.HasField(self.proto_type)
        pb = getattr(self.proto.command, self.proto_type)

        collector = mutations.MutationCollector(pool, self.proto.log)
        with collector.collect():
            try:
                result = self.run(project, pool, pb)
            except:
                self.proto.status = commands_pb2.ExecutedCommand.FAILED
                raise

        self.proto.status = commands_pb2.ExecutedCommand.APPLIED
        return result

    def redo(self, project: pmodel.Project, pool: pmodel.Pool) -> None:
        assert self.proto.status == commands_pb2.ExecutedCommand.APPLIED

        mutation_list = mutations.MutationList(pool, self.proto.log)
        mutation_list.apply_forward()

    def undo(self, project: pmodel.Project, pool: pmodel.Pool) -> None:
        assert self.proto.status == commands_pb2.ExecutedCommand.APPLIED

        mutation_list = mutations.MutationList(pool, self.proto.log)
        mutation_list.apply_backward()
