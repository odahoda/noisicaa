#!/usr/bin/python3

import logging

from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import score_track
from . import track_group
from . import sheet_property_track
from . import pipeline_graph

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
            num_measures = max(num_measures, len(track.measures))

        track_name = "Track %d" % (len(parent_group.tracks) + 1)
        track_cls_map = {
            'score': score_track.ScoreTrack,
            'group': track_group.TrackGroup,
        }
        track_cls = track_cls_map[self.track_type]
        track = track_cls(name=track_name, num_measures=num_measures)
        parent_group.tracks.insert(insert_index, track)

        track.add_to_pipeline()

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

        track.remove_from_pipeline()

        del parent_group.tracks[track.index]

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


class AddPipelineGraphNode(commands.Command):
    name = core.Property(str)
    graph_pos_x = core.Property(int)
    graph_pos_y = core.Property(int)

    def __init__(
            self, name=None, graph_pos_x=None, graph_pos_y=None,
            state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name
            self.graph_pos_x = graph_pos_x
            self.graph_pos_y = graph_pos_y

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        node = pipeline_graph.PipelineGraphNode(
            name=self.name,
            graph_pos_x=self.graph_pos_x,
            graph_pos_y=self.graph_pos_y)
        sheet.pipeline_graph_nodes.append(node)
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

        for idx, node in enumerate(sheet.pipeline_graph_nodes):
            if node.id == self.node_id:
                break
        else:
            raise ValueError("Node %s not found" % self.node_id)

        delete_connections = set()
        for cidx, connection in enumerate(
                sheet.pipeline_graph_connections):
            if connection.source_node is node:
                delete_connections.add(cidx)
            if connection.dest_node is node:
                delete_connections.add(cidx)
        for cidx in sorted(delete_connections, reverse=True):
            del sheet.pipeline_graph_connections[cidx]

        del sheet.pipeline_graph_nodes[idx]

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
        sheet.pipeline_graph_connections.append(connection)
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

        for idx, connection in enumerate(sheet.pipeline_graph_connections):
            if connection.id == self.connection_id:
                break
        else:
            raise ValueError("Connection %s not found" % self.connection_id)

        del sheet.pipeline_graph_connections[idx]

commands.Command.register_command(RemovePipelineGraphConnection)


class Sheet(model.Sheet, state.StateBase):
    def __init__(self, name=None, num_tracks=1, state=None):
        super().__init__(state)

        if state is None:
            self.name = name

            self.master_group = track_group.MasterTrackGroup(name="Master")
            self.property_track = sheet_property_track.SheetPropertyTrack(name="Time")

            for i in range(num_tracks):
                self.master_group.tracks.append(
                    score_track.ScoreTrack(name="Track %d" % i))

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
            max_length = max(len(track.measures) for track in self.all_tracks)
            if max_length < 2:
                break

            can_remove = True
            for track in self.all_tracks:
                if len(track.measures) < max_length:
                    continue
                if not track.measures[max_length - 1].empty:
                    can_remove = False
            if not can_remove:
                break

            for track in self.all_tracks:
                if len(track.measures) < max_length:
                    continue
                track.remove_measure(max_length - 1)

            remove_trailing_empty_measures -= 1

        max_length = max(len(track.measures) for track in self.all_tracks)

        for track in self.all_tracks:
            while len(track.measures) < max_length:
                track.append_measure()

    def handle_pipeline_mutation(self, mutation):
        self.listeners.call('pipeline_mutations', mutation)

    def add_to_pipeline(self):
        self.master_group.add_to_pipeline()

    def remove_from_pipeline(self):
        self.master_group.remove_from_pipeline()


state.StateBase.register_class(Sheet)
