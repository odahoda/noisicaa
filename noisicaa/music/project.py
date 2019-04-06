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
from typing import cast, Any, Optional, Iterator, Type

from noisicaa.core.typing_extra import down_cast
from noisicaa.core import storage as storage_lib
from noisicaa import audioproc
from noisicaa import model
from noisicaa import node_db as node_db_lib
from noisicaa.builtin_nodes import server_registry
from . import pmodel
from . import graph
from . import commands
from . import commands_pb2
from . import base_track
from . import samples

logger = logging.getLogger(__name__)


class Crash(commands.Command):
    proto_type = 'crash'

    def run(self) -> None:
        raise RuntimeError('Boom')


class UpdateProject(commands.Command):
    proto_type = 'update_project'

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateProject, self.pb)

        if pb.HasField('set_bpm'):
            self.pool.project.bpm = pb.set_bpm


# class SetNumMeasures(commands.Command):
#     proto_type = 'set_num_measures'

#     def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
#         pb = down_cast(commands_pb2.SetNumMeasures, pb)

#         raise NotImplementedError
#         # for track in project.all_tracks:
#         #     if not isinstance(track, pmodel.MeasuredTrack):
#         #         continue
#         #     track = cast(base_track.MeasuredTrack, track)

#         #     while len(track.measure_list) < pb.num_measures:
#         #         track.append_measure()

#         #     while len(track.measure_list) > pb.num_measures:
#         #         track.remove_measure(len(track.measure_list) - 1)


class Metadata(pmodel.Metadata):
    pass


class BaseProject(pmodel.Project):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_db = None  # type: node_db_lib.NodeDBClient

        self.command_registry = commands.CommandRegistry()
        self.command_registry.register(Crash)
        self.command_registry.register(UpdateProject)
        self.command_registry.register(graph.CreateNode)
        self.command_registry.register(graph.DeleteNode)
        self.command_registry.register(graph.CreateNodeConnection)
        self.command_registry.register(graph.DeleteNodeConnection)
        self.command_registry.register(graph.UpdateNode)
        self.command_registry.register(graph.UpdatePort)
        self.command_registry.register(base_track.UpdateTrack)
        self.command_registry.register(base_track.CreateMeasure)
        self.command_registry.register(base_track.UpdateMeasure)
        self.command_registry.register(base_track.DeleteMeasure)
        self.command_registry.register(base_track.PasteMeasures)

        server_registry.register_commands(self.command_registry)


    def create(
            self, *,
            node_db: Optional[node_db_lib.NodeDBClient] = None,
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)
        self.node_db = node_db

        self.metadata = self._pool.create(Metadata)

        system_out_node = self._pool.create(
            graph.SystemOutNode,
            name="System Out", graph_pos=model.Pos2F(200, 0))
        self.add_node(system_out_node)

    def close(self) -> None:
        pass

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        return self.node_db.get_node_description(uri)

    def dispatch_command_sequence_proto(self, proto: commands_pb2.CommandSequence) -> None:
        self.dispatch_command_sequence(commands.CommandSequence.create(proto))

    def dispatch_command_sequence(self, sequence: commands.CommandSequence) -> None:
        logger.info("Executing command sequence:\n%s", sequence)
        sequence.apply(self.command_registry, self._pool)
        logger.info(
            "Executed command sequence %s (%d operations)",
            sequence.command_names, sequence.num_log_ops)

    def handle_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        self.pipeline_mutation.call(mutation)

    def add_node(self, node: pmodel.BaseNode) -> None:
        for mutation in node.get_add_mutations():
            self.handle_pipeline_mutation(mutation)
        self.nodes.append(node)

    def remove_node(self, node: pmodel.BaseNode) -> None:
        delete_connections = set()
        for cidx, connection in enumerate(self.node_connections):
            if connection.source_node is node:
                delete_connections.add(cidx)
            if connection.dest_node is node:
                delete_connections.add(cidx)
        for cidx in sorted(delete_connections, reverse=True):
            self.remove_node_connection(self.node_connections[cidx])

        for mutation in node.get_remove_mutations():
            self.handle_pipeline_mutation(mutation)

        del self.nodes[node.index]

    def add_node_connection(self, connection: pmodel.NodeConnection) -> None:
        self.node_connections.append(connection)
        for mutation in connection.get_add_mutations():
            self.handle_pipeline_mutation(mutation)

    def remove_node_connection(self, connection: pmodel.NodeConnection) -> None:
        for mutation in connection.get_remove_mutations():
            self.handle_pipeline_mutation(mutation)
        del self.node_connections[connection.index]

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        for node in self.nodes:
            yield from node.get_add_mutations()
        for connection in self.node_connections:
            yield from connection.get_add_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        for connection in self.node_connections:
            yield from connection.get_remove_mutations()
        for node in self.nodes:
            yield from node.get_remove_mutations()


class Project(BaseProject):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__storage = None  # type: storage_lib.ProjectStorage
        self.__latest_command_sequence = None  # type: commands.CommandSequence
        self.__latest_command_time = None  # type: float

    def create(
            self, *, storage: Optional[storage_lib.ProjectStorage] = None, **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.__storage = storage

    @property
    def closed(self) -> bool:
        return self.__storage is None

    @property
    def path(self) -> Optional[str]:
        if self.__storage:
            return self.__storage.path
        return None

    @property
    def data_dir(self) -> Optional[str]:
        if self.__storage:
            return self.__storage.data_dir
        return None

    @classmethod
    def open(
            cls, *,
            path: str,
            pool: pmodel.Pool,
            node_db: node_db_lib.NodeDBClient) -> 'Project':
        storage = storage_lib.ProjectStorage()
        storage.open(path)

        checkpoint_number, actions = storage.get_restore_info()

        checkpoint_serialized = storage.get_checkpoint(checkpoint_number)
        checkpoint = model.ObjectTree()
        checkpoint.MergeFromString(checkpoint_serialized)

        project = pool.deserialize_tree(checkpoint)
        assert isinstance(project, Project)

        project.node_db = node_db
        project.__storage = storage

        def validate_node(parent: Optional[pmodel.ObjectBase], node: pmodel.ObjectBase) -> None:
            assert node.parent is parent
            assert node.project is project

            for c in node.list_children():
                validate_node(node, cast(pmodel.ObjectBase, c))

        validate_node(None, project)

        for action, log_number in actions:
            sequence_data = storage.get_log_entry(log_number)
            sequence = commands.CommandSequence.deserialize(sequence_data)
            logger.info(
                "Replay action %s of command sequence %s (%d operations)",
                action.name, sequence.command_names, sequence.num_log_ops)

            if action == storage_lib.ACTION_FORWARD:
                sequence.redo(pool)
            elif action == storage_lib.ACTION_BACKWARD:
                sequence.undo(pool)
            else:
                raise ValueError("Unsupported action %s" % action)

        return project

    @classmethod
    def create_blank(
            cls, *,
            path: str,
            pool: pmodel.Pool,
            node_db: node_db_lib.NodeDBClient
    ) -> 'Project':
        storage = storage_lib.ProjectStorage.create(path)

        project = pool.create(cls, storage=storage, node_db=node_db)
        pool.set_root(project)

        # Write initial checkpoint of an empty project.
        project.create_checkpoint()

        return project

    def close(self) -> None:
        self.__flush_commands()

        if self.__storage is not None:
            self.__storage.close()
            self.__storage = None

        self.reset_state()

        super().close()

    def create_checkpoint(self) -> None:
        checkpoint_serialized = self.serialize_object(self)
        self.__storage.add_checkpoint(checkpoint_serialized)

    def serialize_object(self, obj: model.ObjectBase) -> bytes:
        proto = obj.serialize()
        return proto.SerializeToString()

    def __flush_commands(self) -> None:
        if self.__latest_command_sequence is not None:
            self.__storage.append_log_entry(self.__latest_command_sequence.serialize())
            self.__latest_command_sequence = None

        if self.__storage.logs_since_last_checkpoint > 1000:
            self.create_checkpoint()

    def dispatch_command_sequence(self, sequence: commands.CommandSequence) -> None:
        if self.closed:
            raise RuntimeError(
                "Command sequence %s executed on closed project." % sequence.command_names)

        super().dispatch_command_sequence(sequence)

        if not sequence.is_noop:
            if (self.__latest_command_sequence is None
                    or time.time() - self.__latest_command_time > 4
                    or not self.__latest_command_sequence.try_merge_with(sequence)):
                self.__flush_commands()
                self.__latest_command_sequence = sequence
                self.__latest_command_time = time.time()

    def undo(self) -> None:
        if self.closed:
            raise RuntimeError("Undo executed on closed project.")

        self.__flush_commands()

        if self.__storage.can_undo:
            action, sequence_data = self.__storage.get_log_entry_to_undo()
            sequence = commands.CommandSequence.deserialize(sequence_data)
            logger.info(
                "Undo command sequence %s (%d operations)",
                sequence.command_names, sequence.num_log_ops)

            if action == storage_lib.ACTION_FORWARD:
                sequence.redo(self._pool)
            elif action == storage_lib.ACTION_BACKWARD:
                sequence.undo(self._pool)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.__storage.undo()

    def redo(self) -> None:
        if self.closed:
            raise RuntimeError("Redo executed on closed project.")

        self.__flush_commands()

        if self.__storage.can_redo:
            action, sequence_data = self.__storage.get_log_entry_to_redo()
            sequence = commands.CommandSequence.deserialize(sequence_data)
            logger.info(
                "Redo command sequence %s (%d operations)",
                sequence.command_names, sequence.num_log_ops)

            if action == storage_lib.ACTION_FORWARD:
                sequence.redo(self._pool)
            elif action == storage_lib.ACTION_BACKWARD:
                sequence.undo(self._pool)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.__storage.redo()


class Pool(pmodel.Pool):
    def __init__(self, project_cls: Type[Project] = None) -> None:
        super().__init__()

        if project_cls is not None:
            self.register_class(project_cls)
        else:
            self.register_class(Project)

        self.register_class(Metadata)
        self.register_class(samples.Sample)
        self.register_class(base_track.MeasureReference)
        self.register_class(graph.SystemOutNode)
        self.register_class(graph.NodeConnection)
        self.register_class(graph.Node)

        server_registry.register_classes(self)
