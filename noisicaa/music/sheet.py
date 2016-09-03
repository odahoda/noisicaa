#!/usr/bin/python3

import itertools
import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import score_track
from . import beat_track
from . import track_group
from . import sheet_property_track
from . import pipeline_graph
from . import misc
from . import track

logger = logging.getLogger(__name__)


class AddTrack(commands.Command):
    track_type = core.Property(str)
    parent_group_id = core.Property(str)
    insert_index = core.Property(int)

    def __init__(self, track_type=None, parent_group_id=None, insert_index=-1, state=None):
        super().__init__(state=state)
        if state is None:
            self.track_type = track_type
            self.parent_group_id = parent_group_id
            self.insert_index = insert_index

    def run(self, sheet):
        assert isinstance(sheet, Sheet)
        project = sheet.root

        parent_group = project.get_object(self.parent_group_id)
        assert parent_group.is_child_of(sheet)
        assert isinstance(parent_group, track_group.TrackGroup)

        if self.insert_index == -1:
            insert_index = len(parent_group.tracks)
        else:
            insert_index = self.insert_index
            assert 0 <= insert_index <= len(parent_group.tracks)

        num_measures = 1
        for track in parent_group.walk_tracks():
            num_measures = max(num_measures, len(track.measure_list))

        track_name = "Track %d" % (len(parent_group.tracks) + 1)
        track_cls_map = {
            'score': score_track.ScoreTrack,
            'beat': beat_track.BeatTrack,
            'group': track_group.TrackGroup,
        }
        track_cls = track_cls_map[self.track_type]
        track = track_cls(name=track_name, num_measures=num_measures)

        sheet.add_track(parent_group, insert_index, track)

        return insert_index

commands.Command.register_command(AddTrack)


class RemoveTrack(commands.Command):
    track_id = core.Property(str)

    def __init__(self, track_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.track_id = track_id

    def run(self, sheet):
        assert isinstance(sheet, Sheet)
        project = sheet.root

        track = project.get_object(self.track_id)
        assert track.is_child_of(sheet)
        parent_group = track.parent

        sheet.remove_track(parent_group, track)

commands.Command.register_command(RemoveTrack)


class MoveTrack(commands.Command):
    track = core.Property(int)
    direction = core.Property(int)

    def __init__(self, track=None, direction=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.track = track
            self.direction = direction

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        track = sheet.master_group.tracks[self.track]
        assert track.index == self.track

        if self.direction == 0:
            raise ValueError("No direction given.")

        if self.direction < 0:
            if track.index == 0:
                raise ValueError("Can't move first track up.")
            new_pos = track.index - 1
            del sheet.master_group.tracks[track.index]
            sheet.master_group.tracks.insert(new_pos, track)

        elif self.direction > 0:
            if track.index == len(sheet.master_group.tracks) - 1:
                raise ValueError("Can't move last track down.")
            new_pos = track.index + 1
            del sheet.master_group.tracks[track.index]
            sheet.master_group.tracks.insert(new_pos, track)

        return track.index

commands.Command.register_command(MoveTrack)


class InsertMeasure(commands.Command):
    tracks = core.ListProperty(int)
    pos = core.Property(int)

    def __init__(self, tracks=None, pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.tracks.extend(tracks)
            self.pos = pos

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        if not self.tracks:
            sheet.property_track.insert_measure(self.pos)
        else:
            sheet.property_track.append_measure()

        for idx, track in enumerate(sheet.master_group.tracks):
            if not self.tracks or idx in self.tracks:
                track.insert_measure(self.pos)
            else:
                track.append_measure()

commands.Command.register_command(InsertMeasure)


class RemoveMeasure(commands.Command):
    tracks = core.ListProperty(int)
    pos = core.Property(int)

    def __init__(self, tracks=None, pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.tracks.extend(tracks)
            self.pos = pos

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        if not self.tracks:
            sheet.property_track.remove_measure(self.pos)

        for idx, track in enumerate(sheet.master_group.tracks):
            if not self.tracks or idx in self.tracks:
                track.remove_measure(self.pos)
                if self.tracks:
                    track.append_measure()

commands.Command.register_command(RemoveMeasure)


class PasteMeasuresAsLink(commands.Command):
    src_ids = core.ListProperty(str)
    target_ids = core.ListProperty(str)

    def __init__(self, src_ids=None, target_ids=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.src_ids.extend(src_ids)
            self.target_ids.extend(target_ids)

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        root = sheet.root

        src_measures = [root.get_object(obj_id) for obj_id in self.src_ids]
        assert all(isinstance(obj, track.Measure) for obj in src_measures)

        target_measures = [
            root.get_object(obj_id) for obj_id in self.target_ids]
        assert all(
            isinstance(obj, track.MeasureReference) for obj in target_measures)

        affected_track_ids = set(
            obj.track.id for obj in src_measures + target_measures)
        assert len(affected_track_ids) == 1

        t = root.get_object(affected_track_ids.pop())
        logger.info("HEAP:%s", ''.join('\n  %2d %s (%d refs)' % (i, o.id, o.ref_count) for i, o in enumerate(t.measure_heap)))
        logger.info("LIST:%s", ''.join('\n  %2d %s' % (i, o.measure.id) for i, o in enumerate(t.measure_list)))

        for target, src in zip(
                target_measures, itertools.cycle(src_measures)):
            old = target.measure
            old.ref_count -= 1

            target.measure_id = src.id
            target.measure.ref_count += 1

            if old.ref_count == 0:
                logger.info("GC measure %s", old.id)
                del old.track.measure_heap[old.index]

commands.Command.register_command(PasteMeasuresAsLink)


class AddPipelineGraphNode(commands.Command):
    uri = core.Property(str)
    graph_pos = core.Property(misc.Pos2F)

    def __init__(self, uri=None, graph_pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.uri = uri
            self.graph_pos = graph_pos

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        node_desc = sheet.project.get_node_description(self.uri)

        node = pipeline_graph.PipelineGraphNode(
            name=node_desc.display_name,
            node_uri=self.uri,
            graph_pos=self.graph_pos)
        sheet.add_pipeline_graph_node(node)
        return node.id

commands.Command.register_command(AddPipelineGraphNode)


class RemovePipelineGraphNode(commands.Command):
    node_id = core.Property(str)

    def __init__(self, node_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.node_id = node_id

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        root = sheet.root
        node = root.get_object(self.node_id)
        assert node.is_child_of(sheet)

        sheet.remove_pipeline_graph_node(node)

commands.Command.register_command(RemovePipelineGraphNode)


class AddPipelineGraphConnection(commands.Command):
    source_node_id = core.Property(str)
    source_port_name = core.Property(str)
    dest_node_id = core.Property(str)
    dest_port_name = core.Property(str)

    def __init__(
            self,
            source_node_id=None, source_port_name=None,
            dest_node_id=None, dest_port_name=None,
            state=None):
        super().__init__(state=state)
        if state is None:
            self.source_node_id = source_node_id
            self.source_port_name = source_port_name
            self.dest_node_id = dest_node_id
            self.dest_port_name = dest_port_name

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        root = sheet.root

        source_node = root.get_object(self.source_node_id)
        assert source_node.is_child_of(sheet)
        dest_node = root.get_object(self.dest_node_id)
        assert dest_node.is_child_of(sheet)

        connection = pipeline_graph.PipelineGraphConnection(
            source_node=source_node, source_port=self.source_port_name,
            dest_node=dest_node, dest_port=self.dest_port_name)
        sheet.add_pipeline_graph_connection(connection)
        return connection.id

commands.Command.register_command(AddPipelineGraphConnection)


class RemovePipelineGraphConnection(commands.Command):
    connection_id = core.Property(str)

    def __init__(self, connection_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.connection_id = connection_id

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        root = sheet.root
        connection = root.get_object(self.connection_id)
        assert connection.is_child_of(sheet)

        sheet.remove_pipeline_graph_connection(connection)

commands.Command.register_command(RemovePipelineGraphConnection)


class Sheet(model.Sheet, state.StateBase):
    def __init__(self, name=None, num_tracks=1, state=None):
        super().__init__(state)

        if state is None:
            self.name = name

            self.master_group = track_group.MasterTrackGroup(name="Master")
            self.property_track = sheet_property_track.SheetPropertyTrack(name="Time")

            for i in range(num_tracks):
                track = score_track.ScoreTrack(name="Track %d" % i)
                self.add_track(
                    self.master_group, len(self.master_group.tracks),
                    track)

    @property
    def project(self):
        return self.parent

    @property
    def all_tracks(self):
        return ([self.property_track]
                + list(self.master_group.walk_tracks()))

    def clear(self):
        pass

    def equalize_tracks(self, remove_trailing_empty_measures=0):
        if len(self.master_group.tracks) < 1:
            return

        while remove_trailing_empty_measures > 0:
            max_length = max(
                len(track.measure_list) for track in self.all_tracks)
            if max_length < 2:
                break

            can_remove = True
            for track in self.all_tracks:
                if len(track.measure_list) < max_length:
                    continue
                if not track.measure_list[max_length - 1].measure.empty:
                    can_remove = False
            if not can_remove:
                break

            for track in self.all_tracks:
                if len(track.measure_list) < max_length:
                    continue
                track.remove_measure(max_length - 1)

            remove_trailing_empty_measures -= 1

        max_length = max(len(track.measure_list) for track in self.all_tracks)

        for track in self.all_tracks:
            while len(track.measure_list) < max_length:
                track.append_measure()

    def add_track(self, parent_group, insert_index, track):
        parent_group.tracks.insert(insert_index, track)
        track.add_pipeline_nodes()

    def remove_track(self, parent_group, track):
        track.remove_pipeline_nodes()
        del parent_group.tracks[track.index]

    def handle_pipeline_mutation(self, mutation):
        self.listeners.call('pipeline_mutations', mutation)

    @property
    def audio_out_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.AudioOutPipelineGraphNode):
                return node

        raise ValueError("No audio out node found.")

    def add_pipeline_nodes(self):
        audio_out_node = pipeline_graph.AudioOutPipelineGraphNode(
            name="Audio Out", graph_pos=misc.Pos2F(200, 0))
        self.add_pipeline_graph_node(audio_out_node)
        self.master_group.add_pipeline_nodes()

    def remove_pipeline_nodes(self):
        self.master_group.remove_pipeline_nodes()
        self.remove_pipeline_graph_node(self.audio_out_node)

    def add_pipeline_graph_node(self, node):
        self.pipeline_graph_nodes.append(node)
        node.add_to_pipeline()

    def remove_pipeline_graph_node(self, node):
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

        node.remove_from_pipeline()
        del self.pipeline_graph_nodes[node.index]

    def add_pipeline_graph_connection(self, connection):
        self.pipeline_graph_connections.append(connection)
        connection.add_to_pipeline()

    def remove_pipeline_graph_connection(self, connection):
        connection.remove_from_pipeline()
        del self.pipeline_graph_connections[connection.index]

    def add_to_pipeline(self):
        for node in self.pipeline_graph_nodes:
            node.add_to_pipeline()
        for connection in self.pipeline_graph_connections:
            connection.add_to_pipeline()

    def remove_from_pipeline(self):
        for connection in self.pipeline_graph_connections:
            connection.remove_from_pipeline()
        for node in self.pipeline_graph_nodes:
            node.remove_from_pipeline()


state.StateBase.register_class(Sheet)
