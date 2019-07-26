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

import contextlib
import itertools
import logging
import time
from typing import cast, Any, Optional, Dict, Tuple, Iterator, Sequence, Generator, Type

from noisicaa.core.typing_extra import down_cast
from noisicaa.core import storage
from noisicaa import audioproc
from noisicaa import core
from noisicaa import value_types
from noisicaa import node_db as node_db_lib
from . import graph
from . import base_track
from . import samples as samples_lib
from . import metadata as metadata_lib
from . import transfer_function
from . import writer_client
from . import model_base
from . import model_base_pb2
from . import _model
from . import mutations
from . import mutations_pb2

logger = logging.getLogger(__name__)

LOG_VERSION = 1


class BaseProject(_model.Project, model_base.ObjectBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.node_db = None  # type: node_db_lib.NodeDBClient

        self.duration_changed = \
            core.Callback[model_base.PropertyChange[audioproc.MusicalDuration]]()
        self.pipeline_mutation = core.Callback[audioproc.Mutation]()

        self.__time_mapper = audioproc.TimeMapper(44100)
        self.__time_mapper.setup(self)

        self._in_mutation = False

    def create(
            self, *,
            node_db: Optional[node_db_lib.NodeDBClient] = None,
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)
        self.node_db = node_db

        self.metadata = self._pool.create(metadata_lib.Metadata)

        system_out_node = self._pool.create(
            graph.SystemOutNode,
            name="System Out", graph_pos=value_types.Pos2F(200, 0))
        self.add_node(system_out_node)

    def setup(self) -> None:
        super().setup()

        for conn in self.node_connections:
            change = model_base.PropertyListInsert(self, 'node_connections', -1, conn)
            conn.source_node.connections_changed.call(change)
            conn.dest_node.connections_changed.call(change)
        self.node_connections_changed.add(self.__node_connections_changed)

    def __node_connections_changed(
            self, change: model_base.PropertyListChange[graph.NodeConnection]
    ) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            conn = change.new_value
        elif isinstance(change, model_base.PropertyListDelete):
            conn = change.old_value
        else:
            raise ValueError(change)

        conn.source_node.connections_changed.call(change)
        conn.dest_node.connections_changed.call(change)

    @property
    def time_mapper(self) -> audioproc.TimeMapper:
        return self.__time_mapper

    @property
    def project(self) -> 'Project':
        return down_cast(Project, super().project)

    @property
    def system_out_node(self) -> graph.SystemOutNode:
        for node in self.get_property_value('nodes'):
            if isinstance(node, graph.SystemOutNode):
                return node

        raise ValueError("No system out node found.")

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(2 * 120, 4)  # 2min * 120bpm

    @property
    def attached_to_project(self) -> bool:
        return True

    def get_bpm(self, measure_idx: int, tick: int) -> int:  # pylint: disable=unused-argument
        return self.bpm

    @property
    def data_dir(self) -> Optional[str]:
        return None

    async def close(self) -> None:
        pass

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        return self.node_db.get_node_description(uri)

    def monitor_model_changes(self) -> None:
        self._pool.model_changed.add(self.__model_changed)

    def __model_changed(self, change: model_base.PropertyChange) -> None:
        assert self._in_mutation

    @contextlib.contextmanager
    def apply_mutations(self, name: str) -> Generator:
        assert not self._in_mutation
        self._in_mutation = True
        try:
            logger.info("Beginning mutation '%s'...", name)

            mutation_list = mutations_pb2.MutationList(
                version=LOG_VERSION,
                name=name,
                timestamp=time.time(),
            )

            collector = mutations.MutationCollector(self._pool, mutation_list)
            with collector.collect():
                yield

            logger.info("Mutation '%s' finished:\n%s", name, mutation_list)
            self._mutation_list_applied(mutation_list)

        finally:
            self._in_mutation = False

    def _mutation_list_applied(self, mutation_list: mutations_pb2.MutationList) -> None:
        logger.info(str(mutation_list))

    def handle_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        self.pipeline_mutation.call(mutation)

    def create_node(
            self,
            uri: str,
            name: str = None,
            graph_pos: value_types.Pos2F = value_types.Pos2F(0, 0),
            graph_size: value_types.SizeF = value_types.SizeF(200, 100),
            graph_color: value_types.Color = value_types.Color(0.8, 0.8, 0.8),
    ) -> graph.BaseNode:
        node_desc = self.get_node_description(uri)

        kwargs = {
            'name': name or node_desc.display_name,
            'graph_pos': graph_pos,
            'graph_size': graph_size,
            'graph_color': graph_color,
        }

        # Defered import to work around cyclic import.
        from noisicaa.builtin_nodes import model_registry
        try:
            node_cls = model_registry.node_cls_map[uri]
        except KeyError:
            node_cls = graph.Node
            kwargs['node_uri'] = uri

        node = self._pool.create(node_cls, id=None, **kwargs)
        self.add_node(node)
        return node

    def add_node(self, node: graph.BaseNode) -> None:
        for conn in self.node_connections:
            if conn.source_node is node or conn.dest_node is node:
                node.connections_changed.call(
                    model_base.PropertyListInsert(self, 'node_connections', -1, conn))

        for mutation in node.get_add_mutations():
            self.handle_pipeline_mutation(mutation)

        self.nodes.append(node)

    def remove_node(self, node: graph.BaseNode) -> None:
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

    def create_node_connection(
            self,
            source_node: graph.BaseNode,
            source_port: str,
            dest_node: graph.BaseNode,
            dest_port: str,
            type: node_db_lib.PortDescription.Type = node_db_lib.PortDescription.UNDEFINED,  # pylint: disable=redefined-builtin
    ) -> graph.NodeConnection:
        if type == node_db_lib.PortDescription.UNDEFINED:
            type = graph.get_preferred_connection_type(
                source_node, source_port, dest_node, dest_port)
        assert type in source_node.get_possible_port_types(source_port)
        assert type in dest_node.get_possible_port_types(dest_port)

        connection = self._pool.create(
            graph.NodeConnection,
            source_node=source_node, source_port=source_port,
            dest_node=dest_node, dest_port=dest_port,
            type=type)
        self.add_node_connection(connection)
        return connection

    def add_node_connection(self, connection: graph.NodeConnection) -> None:
        self.node_connections.append(connection)
        for mutation in connection.get_add_mutations():
            self.handle_pipeline_mutation(mutation)

    def remove_node_connection(self, connection: graph.NodeConnection) -> None:
        for mutation in connection.get_remove_mutations():
            self.handle_pipeline_mutation(mutation)
        del self.node_connections[connection.index]

    def paste_measures(
            self, *,
            mode: str,
            src_objs: Sequence[model_base_pb2.ObjectTree],
            targets: Sequence[base_track.MeasureReference]
    ) -> None:
        affected_track_ids = set(obj.track.id for obj in targets)
        assert len(affected_track_ids) == 1

        if mode == 'link':
            for target, src_proto in zip(targets, itertools.cycle(src_objs)):
                src = down_cast(base_track.Measure, self._pool[src_proto.root])
                assert src.is_child_of(target.track)
                target.measure = src

        elif mode == 'overwrite':
            measure_map = {}  # type: Dict[int, base_track.Measure]
            for target, src_proto in zip(targets, itertools.cycle(src_objs)):
                try:
                    measure = measure_map[src_proto.root]
                except KeyError:
                    measure = down_cast(base_track.Measure, self._pool.clone_tree(src_proto))
                    measure_map[src_proto.root] = measure
                    target.track.measure_heap.append(measure)

                target.measure = measure

        else:
            raise ValueError(mode)

        for track_id in affected_track_ids:
            cast(base_track.MeasuredTrack, self._pool[track_id]).garbage_collect_measures()

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

        self.__writer = None  # type: writer_client.WriterClient
        self.__logs_since_last_checkpoint = None  # type: int
        self.__latest_mutation_list = None  # type: mutations_pb2.MutationList
        self.__latest_mutation_time = None  # type: float

    def create(
            self, *, writer: Optional[writer_client.WriterClient] = None, **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.__writer = writer

    @property
    def closed(self) -> bool:
        return self.__writer is None

    @property
    def path(self) -> Optional[str]:
        if self.__writer is not None:
            return self.__writer.path
        return None

    @property
    def data_dir(self) -> Optional[str]:
        if self.__writer is not None:
            return self.__writer.data_dir
        return None

    @classmethod
    async def open(
            cls, *,
            path: str,
            pool: 'Pool',
            writer: writer_client.WriterClient,
            node_db: node_db_lib.NodeDBClient
    ) -> 'Project':
        checkpoint_serialized, actions = await writer.open(path)

        checkpoint = model_base_pb2.ObjectTree()
        checkpoint.MergeFromString(checkpoint_serialized)

        project = pool.deserialize_tree(checkpoint)
        assert isinstance(project, Project)

        project.node_db = node_db
        project.__writer = writer

        def validate_node(
                parent: Optional[model_base.ObjectBase], node: model_base.ObjectBase) -> None:
            assert node.parent is parent
            assert node.project is project

            for c in node.list_children():
                validate_node(node, c)

        validate_node(None, project)

        project.__logs_since_last_checkpoint = 0
        for action, mutation_list_serialized in actions:
            project.__apply_mutation_list(
                action,
                project.deserialize_mutation_list(mutation_list_serialized))
            project.__logs_since_last_checkpoint += 1

        return project

    @classmethod
    async def create_blank(
            cls, *,
            path: str,
            pool: 'Pool',
            node_db: node_db_lib.NodeDBClient,
            writer: writer_client.WriterClient
    ) -> 'Project':
        project = pool.create(cls, writer=writer, node_db=node_db)
        pool.set_root(project)

        checkpoint_serialized = project.serialize_object(project)
        await writer.create(path, checkpoint_serialized)
        project.__logs_since_last_checkpoint = 0

        return project

    async def close(self) -> None:
        self.__flush_mutations()

        if self.__writer is not None:
            await self.__writer.close()
            self.__writer = None

        self.reset_state()
        self.__logs_since_last_checkpoint = None

        await super().close()

    def create_checkpoint(self) -> None:
        checkpoint_serialized = self.serialize_object(self)
        self.__writer.write_checkpoint(checkpoint_serialized)
        self.__logs_since_last_checkpoint = 0

    def serialize_object(self, obj: model_base.ObjectBase) -> bytes:
        proto = obj.serialize()
        return proto.SerializeToString()

    def deserialize_mutation_list(
            self, mutation_list_serialized: bytes) -> mutations_pb2.MutationList:
        mutation_list = mutations_pb2.MutationList()
        parsed_bytes = mutation_list.ParseFromString(mutation_list_serialized)  # type: ignore
        assert parsed_bytes == len(mutation_list_serialized)
        assert mutation_list.version == LOG_VERSION
        return mutation_list

    def __flush_mutations(self) -> None:
        if self.__latest_mutation_list is not None:
            self.__writer.write_log(self.__latest_mutation_list.SerializeToString())
            self.__logs_since_last_checkpoint += 1
            self.__latest_mutation_list = None

        if self.__logs_since_last_checkpoint > 1000:
            self.create_checkpoint()

    def __try_merge_mutation_list(self, mutation_list: mutations_pb2.MutationList) -> bool:
        assert self.__latest_mutation_list is not None

        k = None  # type: Tuple[Any, ...]

        property_changes_a = {}  # type: Dict[Tuple[Any, ...], int]
        for op in self.__latest_mutation_list.ops:
            if op.WhichOneof('op') == 'set_property':
                k = (op.set_property.obj_id, op.set_property.prop_name)
                property_changes_a[k] = op.set_property.new_slot
            elif op.WhichOneof('op') == 'list_set':
                k = (op.list_set.obj_id, op.list_set.prop_name, op.list_set.index)
                property_changes_a[k] = op.list_set.new_slot
            else:
                return False

        property_changes_b = {}  # type: Dict[Tuple[Any, ...], int]
        for op in mutation_list.ops:
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

        for k, slot_idx_a in property_changes_a.items():
            slot_a = self.__latest_mutation_list.slots[slot_idx_a]
            slot_b = mutation_list.slots[property_changes_b[k]]
            assert slot_a.WhichOneof('value') == slot_b.WhichOneof('value'), (slot_a, slot_b)
            self.__latest_mutation_list.slots[slot_idx_a].CopyFrom(slot_b)

        return True

    def _mutation_list_applied(self, mutation_list: mutations_pb2.MutationList) -> None:
        if len(mutation_list.ops) != 0:
            if (self.__latest_mutation_list is None
                    or time.time() - self.__latest_mutation_time > 4
                    or not self.__try_merge_mutation_list(mutation_list)):
                self.__flush_mutations()
                self.__latest_mutation_list = mutation_list
                self.__latest_mutation_time = time.time()

    def __apply_mutation_list(
            self,
            action: storage.Action,
            mutation_list_pb: mutations_pb2.MutationList
    ) -> None:
        logger.info(
            "Apply '%s' (%d operations) %s",
            mutation_list_pb.name, len(mutation_list_pb.ops), action.name)

        mutation_list = mutations.MutationList(self._pool, mutation_list_pb)
        try:
            self._in_mutation = True
            if action == storage.ACTION_FORWARD:
                mutation_list.apply_forward()
            else:
                assert action == storage.ACTION_BACKWARD
                mutation_list.apply_backward()

        finally:
            self._in_mutation = False

    async def undo(self) -> None:
        assert not self.closed
        self.__flush_mutations()
        response = await self.__writer.undo()
        if response is not None:
            action, mutation_list_serialized = response
            self.__apply_mutation_list(
                action,
                self.deserialize_mutation_list(mutation_list_serialized))

    async def redo(self) -> None:
        assert not self.closed
        self.__flush_mutations()
        response = await self.__writer.redo()
        if response is not None:
            action, mutation_list_serialized = response
            self.__apply_mutation_list(
                action,
                self.deserialize_mutation_list(mutation_list_serialized))


class Pool(model_base.Pool):
    def __init__(self, project_cls: Type[Project] = None) -> None:
        super().__init__()

        if project_cls is not None:
            self.register_class(project_cls)
        else:
            self.register_class(Project)

        self.register_class(metadata_lib.Metadata)
        self.register_class(samples_lib.Sample)
        self.register_class(base_track.MeasureReference)
        self.register_class(graph.SystemOutNode)
        self.register_class(graph.NodeConnection)
        self.register_class(graph.Node)
        self.register_class(transfer_function.TransferFunction)

        from noisicaa.builtin_nodes import model_registry
        model_registry.register_classes(self)

    @property
    def project(self) -> Project:
        return down_cast(Project, self.root)
