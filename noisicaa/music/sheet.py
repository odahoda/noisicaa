#!/usr/bin/python3

import logging

from noisicaa import core

from .score_track import ScoreTrack
from .sheet_property_track import SheetPropertyTrack
from . import model
from . import state
from . import commands
from . import mutations

logger = logging.getLogger(__name__)


class AddTrack(commands.Command):
    track_type = core.Property(str)

    def __init__(self, track_type=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.track_type = track_type

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        if len(sheet.tracks) > 0:
            num_measures = max(len(track.measures) for track in sheet.tracks)
        else:
            num_measures = 1

        track_name = "Track %d" % (len(sheet.tracks) + 1)
        track_cls_map = {
            'score': ScoreTrack,
        }
        track_cls = track_cls_map[self.track_type]
        track = track_cls(name=track_name, num_measures=num_measures)
        sheet.tracks.append(track)

        track.add_to_pipeline()

        return len(sheet.tracks) - 1

commands.Command.register_command(AddTrack)


class RemoveTrack(commands.Command):
    track = core.Property(int)

    def __init__(self, track=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.track = track

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        track = sheet.tracks[self.track]
        track.remove_from_pipeline()
        del sheet.tracks[self.track]

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

        track = sheet.tracks[self.track]
        assert track.index == self.track

        if self.direction == 0:
            raise ValueError("No direction given.")

        if self.direction < 0:
            if track.index == 0:
                raise ValueError("Can't move first track up.")
            new_pos = track.index - 1
            del sheet.tracks[track.index]
            sheet.tracks.insert(new_pos, track)

        elif self.direction > 0:
            if track.index == len(sheet.tracks) - 1:
                raise ValueError("Can't move last track down.")
            new_pos = track.index + 1
            del sheet.tracks[track.index]
            sheet.tracks.insert(new_pos, track)

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

        for idx, track in enumerate(sheet.tracks):
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

        for idx, track in enumerate(sheet.tracks):
            if not self.tracks or idx in self.tracks:
                track.remove_measure(self.pos)
                if self.tracks:
                    track.append_measure()

commands.Command.register_command(RemoveMeasure)


class Sheet(model.Sheet, state.StateBase):
    def __init__(self, name=None, num_tracks=1, state=None):
        self.listeners = core.CallbackRegistry()
        super().__init__(state)

        if state is None:
            self.name = name

            self.property_track = SheetPropertyTrack(name="Time")

            for i in range(num_tracks):
                self.tracks.append(ScoreTrack(name="Track %d" % i))

    def property_changed(self, change):
        super().property_changed(change)
        self.listeners.call(change.prop_name, change)

    @property
    def project(self):
        return self.parent

    @property
    def all_tracks(self):
        return [self.property_track] + list(self.tracks)

    def clear(self):
        pass

    def equalize_tracks(self, remove_trailing_empty_measures=0):
        if len(self.tracks) < 1:
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

    @property
    def main_mixer_name(self):
        return '%s-sheet-mixer' % self.id

    def add_to_pipeline(self):
        self.handle_pipeline_mutation(
            mutations.AddNode(
                'passthru', self.main_mixer_name, 'sheet-mixer'))
        self.handle_pipeline_mutation(
            mutations.ConnectPorts(
                self.main_mixer_name, 'out', 'sink', 'in'))

        for track in self.tracks:
            track.add_to_pipeline()

    def remove_from_pipeline(self):
        for track in self.tracks:
            track.remove_from_pipeline()

        self.handle_pipeline_mutation(
            mutations.DisconnectPorts(
                self.main_mixer_name, 'out', 'sink', 'in'))
        self.handle_pipeline_mutation(
            mutations.RemoveNode(self.main_mixer_name))

state.StateBase.register_class(Sheet)
