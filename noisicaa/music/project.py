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

import itertools
import logging
from typing import cast, Any, Optional, Iterator, Dict, Tuple, Type  # pylint: disable=unused-import

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa.core import storage as storage_lib
from noisicaa import audioproc
from noisicaa import model
from noisicaa import node_db as node_db_lib
from . import pmodel
from . import pipeline_graph
from . import property_track
from . import track_group
from . import commands
from . import commands_pb2
from . import score_track
from . import beat_track
from . import control_track
from . import sample_track
from . import base_track

logger = logging.getLogger(__name__)


class UpdateProjectProperties(commands.Command):
    proto_type = 'update_project_properties'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.UpdateProjectProperties, pb)

        if pb.HasField('bpm'):
            project.bpm = pb.bpm

commands.Command.register_command(UpdateProjectProperties)


class AddTrack(commands.Command):
    proto_type = 'add_track'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> int:
        pb = down_cast(commands_pb2.AddTrack, pb)

        parent_group = pool[pb.parent_group_id]
        assert parent_group.is_child_of(project)
        assert isinstance(parent_group, track_group.TrackGroup)

        if pb.insert_index == -1:
            insert_index = len(parent_group.tracks)
        else:
            insert_index = pb.insert_index
            assert 0 <= insert_index <= len(parent_group.tracks)

        track_name = "Track %d" % (len(parent_group.tracks) + 1)
        track_cls_map = {
            'score': score_track.ScoreTrack,
            'beat': beat_track.BeatTrack,
            'control': control_track.ControlTrack,
            'sample': sample_track.SampleTrack,
            'group': track_group.TrackGroup,
        }
        track_cls = track_cls_map[pb.track_type]

        kwargs = {}
        if issubclass(track_cls, pmodel.MeasuredTrack):
            num_measures = 1
            for track in parent_group.walk_tracks():
                if isinstance(track, pmodel.MeasuredTrack):
                    num_measures = max(num_measures, len(track.measure_list))
            kwargs['num_measures'] = num_measures

        track = pool.create(track_cls, name=track_name, **kwargs)

        project.add_track(parent_group, insert_index, track)

        return insert_index

commands.Command.register_command(AddTrack)


class RemoveTrack(commands.Command):
    proto_type = 'remove_track'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveTrack, pb)

        track = cast(pmodel.Track, pool[pb.track_id])
        assert track.is_child_of(project)
        parent_group = cast(pmodel.TrackGroup, track.parent)

        project.remove_track(parent_group, track)

commands.Command.register_command(RemoveTrack)


class InsertMeasure(commands.Command):
    proto_type = 'insert_measure'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.InsertMeasure, pb)

        if not pb.tracks:
            cast(property_track.PropertyTrack, project.property_track).insert_measure(pb.pos)
        else:
            cast(property_track.PropertyTrack, project.property_track).append_measure()

        for track in project.master_group.walk_tracks():
            if not isinstance(track, base_track.MeasuredTrack):
                continue

            if not pb.tracks or track.id in pb.tracks:
                track.insert_measure(pb.pos)
            else:
                track.append_measure()

commands.Command.register_command(InsertMeasure)


class RemoveMeasure(commands.Command):
    proto_type = 'remove_measure'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveMeasure, pb)

        if not pb.tracks:
            cast(property_track.PropertyTrack, project.property_track).remove_measure(pb.pos)

        for idx, track in enumerate(project.master_group.tracks):
            track = cast(base_track.MeasuredTrack, track)
            if not pb.tracks or idx in pb.tracks:
                track.remove_measure(pb.pos)
                if pb.tracks:
                    track.append_measure()

commands.Command.register_command(RemoveMeasure)


class SetNumMeasures(commands.Command):
    proto_type = 'set_num_measures'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetNumMeasures, pb)

        for track in project.all_tracks:
            if not isinstance(track, pmodel.MeasuredTrack):
                continue
            track = cast(base_track.MeasuredTrack, track)

            while len(track.measure_list) < pb.num_measures:
                track.append_measure()

            while len(track.measure_list) > pb.num_measures:
                track.remove_measure(len(track.measure_list) - 1)

commands.Command.register_command(SetNumMeasures)


class ClearMeasures(commands.Command):
    proto_type = 'clear_measures'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.ClearMeasures, pb)

        measure_references = [
            cast(base_track.MeasureReference, pool[obj_id])
            for obj_id in pb.measure_ids]
        assert all(isinstance(obj, base_track.MeasureReference) for obj in measure_references)

        affected_track_ids = set(obj.track.id for obj in measure_references)

        for mref in measure_references:
            track = cast(base_track.MeasuredTrack, mref.track)
            measure = track.create_empty_measure(mref.measure)
            track.measure_heap.append(measure)
            mref.measure = measure

        for track_id in affected_track_ids:
            cast(base_track.MeasuredTrack, pool[track_id]).garbage_collect_measures()

commands.Command.register_command(ClearMeasures)


class PasteMeasures(commands.Command):
    proto_type = 'paste_measures'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.PasteMeasures, pb)

        target_measures = [
            cast(pmodel.MeasureReference, pool[obj_id])
            for obj_id in pb.target_ids]
        assert all(isinstance(obj, pmodel.MeasureReference) for obj in target_measures)

        affected_track_ids = set(obj.track.id for obj in target_measures)
        assert len(affected_track_ids) == 1

        if pb.mode == 'link':
            for target, src_proto in zip(target_measures, itertools.cycle(pb.src_objs)):
                src = down_cast(pmodel.Measure, pool[src_proto.root])
                assert src.is_child_of(target.track)
                target.measure = src

        elif pb.mode == 'overwrite':
            measure_map = {}  # type: Dict[int, pmodel.Measure]
            for target, src_proto in zip(target_measures, itertools.cycle(pb.src_objs)):
                try:
                    measure = measure_map[src_proto.root]
                except KeyError:
                    measure = down_cast(pmodel.Measure, pool.clone_tree(src_proto))
                    measure_map[src_proto.root] = measure
                    cast(pmodel.MeasuredTrack, target.track).measure_heap.append(measure)

                target.measure = measure

        else:
            raise ValueError(pb.mode)

        for track_id in affected_track_ids:
            cast(pmodel.MeasuredTrack, pool[track_id]).garbage_collect_measures()

commands.Command.register_command(PasteMeasures)


class AddPipelineGraphNode(commands.Command):
    proto_type = 'add_pipeline_graph_node'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> int:
        pb = down_cast(commands_pb2.AddPipelineGraphNode, pb)

        node_desc = project.get_node_description(pb.uri)

        node = pool.create(
            pipeline_graph.PipelineGraphNode,
            name=node_desc.display_name,
            node_uri=pb.uri,
            graph_pos=model.Pos2F.from_proto(pb.graph_pos))
        project.add_pipeline_graph_node(node)
        return node.id

commands.Command.register_command(AddPipelineGraphNode)


class RemovePipelineGraphNode(commands.Command):
    proto_type = 'remove_pipeline_graph_node'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemovePipelineGraphNode, pb)

        node = down_cast(pmodel.BasePipelineGraphNode, pool[pb.node_id])
        assert node.is_child_of(project)

        project.remove_pipeline_graph_node(node)

commands.Command.register_command(RemovePipelineGraphNode)


class AddPipelineGraphConnection(commands.Command):
    proto_type = 'add_pipeline_graph_connection'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> int:
        pb = down_cast(commands_pb2.AddPipelineGraphConnection, pb)

        source_node = down_cast(pmodel.BasePipelineGraphNode, pool[pb.source_node_id])
        assert source_node.is_child_of(project)
        dest_node = down_cast(pmodel.BasePipelineGraphNode, pool[pb.dest_node_id])
        assert dest_node.is_child_of(project)

        connection = pool.create(
            pipeline_graph.PipelineGraphConnection,
            source_node=source_node, source_port=pb.source_port_name,
            dest_node=dest_node, dest_port=pb.dest_port_name)
        project.add_pipeline_graph_connection(connection)
        return connection.id

commands.Command.register_command(AddPipelineGraphConnection)


class RemovePipelineGraphConnection(commands.Command):
    proto_type = 'remove_pipeline_graph_connection'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemovePipelineGraphConnection, pb)

        connection = cast(pmodel.PipelineGraphConnection, pool[pb.connection_id])
        assert connection.is_child_of(project)

        project.remove_pipeline_graph_connection(connection)

commands.Command.register_command(RemovePipelineGraphConnection)


class Metadata(pmodel.Metadata):
    pass


class BaseProject(pmodel.Project):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_db = None  # type: node_db_lib.NodeDBClient
        self._duration = None  # type: audioproc.MusicalDuration

    def create(self, *, node_db: Optional[node_db_lib.NodeDBClient] = None, **kwargs: Any) -> None:
        super().create(**kwargs)
        self.node_db = node_db
        self.metadata = self._pool.create(Metadata)
        self.master_group = self._pool.create(track_group.MasterTrackGroup, name="Master")
        self.property_track = self._pool.create(property_track.PropertyTrack, name="Time")

        audio_out_node = self._pool.create(
            pipeline_graph.AudioOutPipelineGraphNode,
            name="Audio Out", graph_pos=model.Pos2F(200, 0))
        self.add_pipeline_graph_node(audio_out_node)
        self.master_group.add_pipeline_nodes()

    def setup(self) -> None:
        super().setup()
        self._duration = self.master_group.duration
        self.master_group.listeners.add('duration_changed', self._on_duration_changed)

    def close(self) -> None:
        pass

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self._duration

    def _on_duration_changed(self) -> None:
        old_duration = self._duration
        new_duration = self.master_group.duration
        if new_duration != self._duration:
            self._duration = new_duration
            self.listeners.call(
                'duration', model.PropertyValueChange('duration', old_duration, new_duration))

    def get_node_description(self, uri: str) -> node_db_lib.NodeDescription:
        return self.node_db.get_node_description(uri)

    def dispatch_command_proto(self, proto: commands_pb2.Command) -> Any:
        return self.dispatch_command(commands.Command.create(proto))

    def dispatch_command(self, cmd: commands.Command) -> Any:
        result = cmd.apply(self, self._pool)
        logger.info("Executed command %s (%d operations)", cmd, cmd.num_log_ops)
        return result

    def add_track(
            self, parent_group: pmodel.TrackGroup, insert_index: int, track: pmodel.Track) -> None:
        parent_group.tracks.insert(insert_index, track)
        track.add_pipeline_nodes()

    def remove_track(self, parent_group: pmodel.TrackGroup, track: pmodel.Track) -> None:
        track.remove_pipeline_nodes()
        del parent_group.tracks[track.index]

    def handle_pipeline_mutation(self, mutation: audioproc.Mutation) -> None:
        self.listeners.call('pipeline_mutations', mutation)

    @property
    def audio_out_node(self) -> pmodel.AudioOutPipelineGraphNode:
        for node in self.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.AudioOutPipelineGraphNode):
                return node

        raise ValueError("No audio out node found.")

    def add_pipeline_graph_node(self, node: pmodel.BasePipelineGraphNode) -> None:
        self.pipeline_graph_nodes.append(node)
        for mutation in node.get_add_mutations():
            self.handle_pipeline_mutation(mutation)

    def remove_pipeline_graph_node(self, node: pmodel.BasePipelineGraphNode) -> None:
        delete_connections = set()
        for cidx, connection in enumerate(
                self.pipeline_graph_connections):
            if connection.source_node is node:
                delete_connections.add(cidx)
            if connection.dest_node is node:
                delete_connections.add(cidx)
        for cidx in sorted(delete_connections, reverse=True):
            self.remove_pipeline_graph_connection(
                self.pipeline_graph_connections[cidx])

        for mutation in node.get_remove_mutations():
            self.handle_pipeline_mutation(mutation)

        del self.pipeline_graph_nodes[node.index]

    def add_pipeline_graph_connection(self, connection: pmodel.PipelineGraphConnection) -> None:
        self.pipeline_graph_connections.append(connection)
        for mutation in connection.get_add_mutations():
            self.handle_pipeline_mutation(mutation)

    def remove_pipeline_graph_connection(self, connection: pmodel.PipelineGraphConnection) -> None:
        for mutation in connection.get_remove_mutations():
            self.handle_pipeline_mutation(mutation)
        del self.pipeline_graph_connections[connection.index]

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        for node in self.pipeline_graph_nodes:
            yield from node.get_add_mutations()
        for connection in self.pipeline_graph_connections:
            yield from connection.get_add_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        for connection in self.pipeline_graph_connections:
            yield from connection.get_remove_mutations()
        for node in self.pipeline_graph_nodes:
            yield from node.get_remove_mutations()


class Project(BaseProject):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.storage = None  # type: storage_lib.ProjectStorage

    def create(
            self, *, storage: Optional[storage_lib.ProjectStorage] = None, **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.storage = storage

    @property
    def closed(self) -> bool:
        return self.storage is None

    @property
    def path(self) -> Optional[str]:
        if self.storage:
            return self.storage.path
        return None

    @property
    def data_dir(self) -> Optional[str]:
        if self.storage:
            return self.storage.data_dir
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
        project.storage = storage

        def validate_node(parent: Optional[pmodel.ObjectBase], node: pmodel.ObjectBase) -> None:
            assert node.parent is parent
            assert node.project is project

            for c in node.list_children():
                validate_node(node, cast(pmodel.ObjectBase, c))

        validate_node(None, project)

        for action, log_number in actions:
            cmd_data = storage.get_log_entry(log_number)
            cmd = commands.Command.deserialize(cmd_data)
            logger.info(
                "Replay action %s of command %s (%d operations)",
                action.name, cmd, cmd.num_log_ops)

            if action == storage_lib.ACTION_FORWARD:
                cmd.redo(project, pool)
            elif action == storage_lib.ACTION_BACKWARD:
                cmd.undo(project, pool)
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

        # Write initial checkpoint of an empty project.
        project.create_checkpoint()

        return project

    def close(self) -> None:
        if self.storage is not None:
            self.storage.close()
            self.storage = None

        self.listeners.clear()
        self.reset_state()

        super().close()

    def create_checkpoint(self) -> None:
        checkpoint_serialized = self.serialize_object(self)
        self.storage.add_checkpoint(checkpoint_serialized)

    def serialize_object(self, obj: model.ObjectBase) -> bytes:
        proto = obj.serialize()
        return proto.SerializeToString()

    def dispatch_command(self, cmd: commands.Command) -> Any:
        if self.closed:
            raise RuntimeError(
                "Command %s executed on closed project." % cmd)

        result = super().dispatch_command(cmd)

        if not cmd.is_noop:
            self.storage.append_log_entry(cmd.serialize())

            if self.storage.logs_since_last_checkpoint > 1000:
                self.create_checkpoint()

        return result

    def undo(self) -> None:
        if self.closed:
            raise RuntimeError("Undo executed on closed project.")

        if self.storage.can_undo:
            action, cmd_data = self.storage.get_log_entry_to_undo()
            cmd = commands.Command.deserialize(cmd_data)
            logger.info("Undo command %s (%d operations)", cmd, cmd.num_log_ops)

            if action == storage_lib.ACTION_FORWARD:
                cmd.redo(self, self._pool)
            elif action == storage_lib.ACTION_BACKWARD:
                cmd.undo(self, self._pool)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.storage.undo()

    def redo(self) -> None:
        if self.closed:
            raise RuntimeError("Redo executed on closed project.")

        if self.storage.can_redo:
            action, cmd_data = self.storage.get_log_entry_to_redo()
            cmd = commands.Command.deserialize(cmd_data)
            logger.info("Redo command %s (%d operations)", cmd, cmd.num_log_ops)

            if action == storage_lib.ACTION_FORWARD:
                cmd.redo(self, self._pool)
            elif action == storage_lib.ACTION_BACKWARD:
                cmd.undo(self, self._pool)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.storage.redo()


class Pool(pmodel.Pool):
    def __init__(self, project_cls: Type[Project] = None) -> None:
        super().__init__()

        if project_cls is not None:
            self.register_class(project_cls)
        else:
            self.register_class(Project)

        self.register_class(Metadata)
        self.register_class(base_track.MeasureReference)
        self.register_class(beat_track.Beat)
        self.register_class(beat_track.BeatMeasure)
        self.register_class(beat_track.BeatTrack)
        self.register_class(control_track.ControlPoint)
        self.register_class(control_track.ControlTrack)
        self.register_class(pipeline_graph.AudioOutPipelineGraphNode)
        self.register_class(pipeline_graph.CVGeneratorPipelineGraphNode)
        self.register_class(pipeline_graph.InstrumentPipelineGraphNode)
        self.register_class(pipeline_graph.PianoRollPipelineGraphNode)
        self.register_class(pipeline_graph.PipelineGraphConnection)
        self.register_class(pipeline_graph.PipelineGraphControlValue)
        self.register_class(pipeline_graph.PipelineGraphNode)
        self.register_class(pipeline_graph.SampleScriptPipelineGraphNode)
        self.register_class(pipeline_graph.TrackMixerPipelineGraphNode)
        self.register_class(property_track.PropertyMeasure)
        self.register_class(property_track.PropertyTrack)
        self.register_class(sample_track.Sample)
        self.register_class(sample_track.SampleRef)
        self.register_class(sample_track.SampleTrack)
        self.register_class(score_track.Note)
        self.register_class(score_track.ScoreMeasure)
        self.register_class(score_track.ScoreTrack)
        self.register_class(track_group.MasterTrackGroup)
        self.register_class(track_group.TrackGroup)
