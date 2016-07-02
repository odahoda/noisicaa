#!/usr/bin/python3

import logging
import os
import os.path
import time
import json

import portalocker

from noisicaa import core
from noisicaa.core import fileutil

from .exceptions import (
    CorruptedProjectError,
    FileOpenError,
    UnsupportedFileVersionError,
)
from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from .time_signature import TimeSignature
from .track import Track
from .score_track import ScoreTrack, Note
from .sheet_property_track import SheetPropertyTrack
from .time import Duration
from . import model
from . import state
from . import commands
from . import instrument

logger = logging.getLogger(__name__)


class AddSheet(commands.Command):
    name = core.Property(str, allow_none=True)

    def __init__(self, name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name

    def run(self, project):
        assert isinstance(project, BaseProject)

        if self.name is not None:
            name = self.name
        else:
            idx = 1
            while True:
                name = 'Sheet %d' % idx
                if name not in [sheet.name for sheet in project.sheets]:
                    break
                idx += 1

        if name in [s.name for s in project.sheets]:
            raise ValueError("Sheet %s already exists" % name)
        sheet = Sheet(name)
        project.sheets.append(sheet)

commands.Command.register_command(AddSheet)


class ClearSheet(commands.Command):
    name = core.Property(str)

    def __init__(self, name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name

    def run(self, project):
        assert isinstance(project, BaseProject)

        project.get_sheet(self.name).clear()

commands.Command.register_command(ClearSheet)


class DeleteSheet(commands.Command):
    name = core.Property(str)

    def __init__(self, name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name

    def run(self, project):
        assert isinstance(project, BaseProject)

        assert len(project.sheets) > 1
        for idx, sheet in enumerate(project.sheets):
            if sheet.name == self.name:
                del project.sheets[idx]
                project.current_sheet = min(
                    project.current_sheet, len(project.sheets) - 1)
                return

        raise ValueError("No sheet %r" % self.name)

commands.Command.register_command(DeleteSheet)


class RenameSheet(commands.Command):
    name = core.Property(str)
    new_name = core.Property(str)

    def __init__(self, name=None, new_name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name
            self.new_name = new_name

    def run(self, project):
        assert isinstance(project, BaseProject)

        if self.name == self.new_name:
            return

        if self.new_name in [s.name for s in project.sheets]:
            raise ValueError("Sheet %s already exists" % self.new_name)

        sheet = project.get_sheet(self.name)
        sheet.name = self.new_name

commands.Command.register_command(RenameSheet)


class SetCurrentSheet(commands.Command):
    name = core.Property(str)

    def __init__(self, name=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name

    def run(self, project):
        assert isinstance(project, BaseProject)

        project.current_sheet = project.get_sheet_index(self.name)

commands.Command.register_command(SetCurrentSheet)


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
        super().__init__(state)
        if state is None:
            self.name = name

            self.property_track = SheetPropertyTrack(name="Time")

            for i in range(num_tracks):
                self.tracks.append(ScoreTrack(name="Track %d" % i))

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

state.StateBase.register_class(Sheet)


class Metadata(model.Metadata, state.StateBase):
    pass

state.StateBase.register_class(Metadata)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=method-hidden
        if isinstance(obj, Duration):
            return {'__type__': 'Duration',
                    'value': [obj.numerator, obj.denominator]}
        if isinstance(obj, Pitch):
            return {'__type__': 'Pitch',
                    'value': [obj.name]}
        if isinstance(obj, Clef):
            return {'__type__': 'Clef',
                    'value': [obj.value]}
        if isinstance(obj, KeySignature):
            return {'__type__': 'KeySignature',
                    'value': [obj.name]}
        if isinstance(obj, TimeSignature):
            return {'__type__': 'TimeSignature',
                    'value': [obj.upper, obj.lower]}
        return super().default(obj)


class JSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, obj):  # pylint: disable=method-hidden
        objtype = obj.get('__type__', None)
        if objtype == 'Duration':
            return Duration(*obj['value'])
        if objtype == 'Pitch':
            return Pitch(*obj['value'])
        if objtype == 'Clef':
            return Clef(*obj['value'])
        if objtype == 'KeySignature':
            return KeySignature(*obj['value'])
        if objtype == 'TimeSignature':
            return TimeSignature(*obj['value'])
        return obj


class BaseProject(model.Project, state.RootMixin, state.StateBase):
    SERIALIZED_CLASS_NAME = 'Project'

    def __init__(self, num_sheets=1, state=None):
        self._mutation_callback = None

        super().__init__(state)
        if state is None:
            self.metadata = Metadata()

            for i in range(1, num_sheets + 1):
                self.sheets.append(Sheet(name="Sheet %d" % i))

    def set_mutation_callback(self, callback):
        assert self._mutation_callback is None
        self._mutation_callback = callback

    def dispatch_command(self, obj_id, cmd):
        obj = self.get_object(obj_id)
        result = cmd.run(obj)
        logger.info("Executed command %s on %s", cmd, obj_id)
        return result

    def handle_mutation(self, mutation):
        if self._mutation_callback is not None:
            self._mutation_callback(mutation)

    @classmethod
    def make_demo(cls):
        project = cls(num_sheets=0)
        sheet = Sheet(name="Demo Sheet", num_tracks=0)
        project.sheets.append(sheet)

        while len(sheet.property_track.measures) < 5:
            sheet.property_track.append_measure()

        for m in sheet.property_track.measures:
            m.bpm = 140

        instr1 = instrument.SoundFontInstrument(
            name="Flute",
            path='/usr/share/sounds/sf2/FluidR3_GM.sf2', bank=0, preset=73)
        track1 = ScoreTrack(name="Track 1", instrument=instr1, num_measures=5)
        sheet.tracks.append(track1)

        instr2 = instrument.SoundFontInstrument(
            name="Yamaha Grand Piano",
            path='/usr/share/sounds/sf2/FluidR3_GM.sf2', bank=0, preset=0)
        track2 = ScoreTrack(name="Track 2", instrument=instr2, num_measures=5)
        sheet.tracks.append(track2)

        track1.measures[0].notes.append(
            Note(pitches=[Pitch('C5')], base_duration=Duration(1, 4)))
        track1.measures[0].notes.append(
            Note(pitches=[Pitch('D5')], base_duration=Duration(1, 4)))
        track1.measures[0].notes.append(
            Note(pitches=[Pitch('E5')], base_duration=Duration(1, 4)))
        track1.measures[0].notes.append(
            Note(pitches=[Pitch('F5')], base_duration=Duration(1, 4)))

        track1.measures[1].notes.append(
            Note(pitches=[Pitch('C5')], base_duration=Duration(1, 2)))
        track1.measures[1].notes.append(
            Note(pitches=[Pitch('F5')], base_duration=Duration(1, 8)))
        track1.measures[1].notes.append(
            Note(pitches=[Pitch('E5')], base_duration=Duration(1, 8)))
        track1.measures[1].notes.append(
            Note(pitches=[Pitch('D5')], base_duration=Duration(1, 4)))

        track1.measures[2].notes.append(
            Note(pitches=[Pitch('C5')], base_duration=Duration(1, 4)))
        track1.measures[2].notes.append(
            Note(pitches=[Pitch('D5')], base_duration=Duration(1, 4)))
        track1.measures[2].notes.append(
            Note(pitches=[Pitch('E5')], base_duration=Duration(1, 4)))
        track1.measures[2].notes.append(
            Note(pitches=[Pitch('F5')], base_duration=Duration(1, 4)))

        track1.measures[3].notes.append(
            Note(pitches=[Pitch('C5')], base_duration=Duration(1, 2)))
        track1.measures[3].notes.append(
            Note(pitches=[Pitch('F5')], base_duration=Duration(1, 8)))
        track1.measures[3].notes.append(
            Note(pitches=[Pitch('E5')], base_duration=Duration(1, 8)))
        track1.measures[3].notes.append(
            Note(pitches=[Pitch('D5')], base_duration=Duration(1, 4)))

        track1.measures[4].notes.append(
            Note(pitches=[Pitch('C5')], base_duration=Duration(1, 1)))


        track2.measures[0].notes.append(
            Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
                 base_duration=Duration(1, 1)))
        track2.measures[1].notes.append(
            Note(pitches=[Pitch('F3'), Pitch('A4'), Pitch('C4')],
                 base_duration=Duration(1, 1)))

        track2.measures[2].notes.append(
            Note(pitches=[Pitch('A3'), Pitch('C4'), Pitch('E4')],
                 base_duration=Duration(1, 1)))
        track2.measures[3].notes.append(
            Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
                 base_duration=Duration(1, 1)))

        track2.measures[4].notes.append(
            Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
                 base_duration=Duration(1, 1)))

        return project


class Project(BaseProject):
    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    def __init__(self, state=None):
        super().__init__(state=state)

        self.file_lock = None
        self.header_data = None
        self.path = None
        self.data_dir = None
        self.command_log_fp = None
        self.checkpoint_sequence_number = 1

    @property
    def closed(self):
        return self.path is None

    def open(self, path):
        assert self.path is None

        path = os.path.abspath(path)
        logger.info("Opening project at %s", path)

        try:
            fp = fileutil.File(path)
            file_info, data = fp.read_json()
        except fileutil.Error as exc:
            raise FileOpenError(str(exc))

        if file_info.filetype != 'project-header':
            raise FileOpenError("Not a project file")

        if file_info.version not in self.SUPPORTED_VERSIONS:
            raise UnsupportedFileVersionError()

        data_dir = os.path.join(os.path.dirname(path), data['data_dir'])
        if not os.path.isdir(data_dir):
            raise CorruptedProjectError("Directory %s missing" % data_dir)

        file_lock = self.acquire_file_lock(os.path.join(data_dir, "lock"))

        try:
            fp = fileutil.File(os.path.join(data_dir, 'state.latest'))
            file_info, state_data = fp.read_json()
        except fileutil.Error as exc:
            raise FileOpenError(str(exc))

        if file_info.filetype != 'project-state':
            raise CorruptedProjectError("File %s corrupted.")

        if file_info.version not in self.SUPPORTED_VERSIONS:
            raise UnsupportedFileVersionError()

        checkpoint_sequence_number = state_data['sequence_number']
        checkpoint_path = os.path.join(data_dir, state_data['checkpoint'])
        command_log_path = os.path.join(data_dir, state_data['log'])

        self.read_checkpoint(checkpoint_path)
        self.replay_command_log(command_log_path)

        command_log_fp = fileutil.MimeLogFile(command_log_path, 'a')

        self.file_lock = file_lock
        self.path = path
        self.data_dir = data_dir
        self.header_data = data
        self.command_log_fp = command_log_fp
        self.checkpoint_sequence_number = checkpoint_sequence_number

    def create(self, path):
        assert self.path is None

        header_data = {
            'created': int(time.time()),
            'data_dir': os.path.splitext(os.path.basename(path))[0] + '.data',
        }
        data_dir = os.path.join(os.path.dirname(path), header_data['data_dir'])

        os.mkdir(data_dir)
        fp = fileutil.File(path)
        fp.write_json(
            header_data,
            fileutil.FileInfo(filetype='project-header',
                              version=self.VERSION))

        state_data, command_log_fp = self.write_checkpoint(data_dir, 1)
        fp = fileutil.File(os.path.join(data_dir, 'state.latest'))
        fp.write_json(
            state_data,
            fileutil.FileInfo(filetype='project-state',
                              version=self.VERSION))

        file_lock = self.acquire_file_lock(os.path.join(data_dir, "lock"))

        self.file_lock = file_lock
        self.path = path
        self.data_dir = data_dir
        self.header_data = header_data
        self.command_log_fp = command_log_fp
        self.checkpoint_sequence_number = 1

    def create_checkpoint(self):
        state_data, command_log_fp = self.write_checkpoint(
            self.data_dir, self.checkpoint_sequence_number + 1)

        fp = fileutil.File(os.path.join(self.data_dir, 'state.latest.new'))
        fp.write_json(
            state_data,
            fileutil.FileInfo(filetype='project-state',
                              version=self.VERSION))
        os.rename(os.path.join(self.data_dir, 'state.latest.new'),
                  os.path.join(self.data_dir, 'state.latest'))

        if self.command_log_fp is not None:
            self.command_log_fp.close()
            self.command_log_fp = None

        self.command_log_fp = command_log_fp
        self.checkpoint_sequence_number += 1

        return state_data['checkpoint']

    def close(self):
        if self.command_log_fp is not None:
            self.command_log_fp.close()

        if self.file_lock is not None:
            self.release_file_lock(self.file_lock)

        self.command_log_fp = None
        self.file_lock = None
        self.header_data = None
        self.path = None
        self.data_dir = None

        self._mutation_callback = None

        self.reset_state()

    def acquire_file_lock(self, lock_path):
        logger.info("Aquire file lock (%s).", lock_path)
        lock_fp = open(lock_path, 'wb')
        portalocker.lock(lock_fp, portalocker.LOCK_EX | portalocker.LOCK_NB)
        return lock_fp

    def release_file_lock(self, lock_fp):
        logger.info("Releasing file lock.")
        lock_fp.close()

    def read_checkpoint(self, path):
        logger.info("Reading checkpoint from %s", path)

        fp = fileutil.File(path)
        file_info, checkpoint = fp.read_json(decoder=JSONDecoder)
        if file_info.filetype != 'project-checkpoint':
            raise FileOpenError("Not a checkpoint file")

        if file_info.version not in self.SUPPORTED_VERSIONS:
            raise UnsupportedFileVersionError()

        self.deserialize(checkpoint)
        self.init_references()

        def validateNode(root, parent, node):
            assert node.parent is parent, (node.parent, parent)
            assert node.root is root, (node.root, root)

            for c in node.list_children():
                validateNode(root, node, c)

        validateNode(self, None, self)

    def replay_command_log(self, command_log_path):
        with fileutil.MimeLogFile(command_log_path, 'r') as fp:
            for serialized, headers, entry_type in fp:
                if entry_type != b'C':
                    raise CorruptedProjectError(
                        "Unexpected log entry type %s" % entry_type)
                obj_id = headers['Target']
                cmd_state = json.loads(serialized, cls=JSONDecoder)
                cmd = commands.Command.create_from_state(cmd_state)
                logger.info("Replay command %s on %s", cmd, obj_id)
                super().dispatch_command(obj_id, cmd)

    def write_checkpoint(self, data_dir, sequence_number):
        name_base = 'state.%d' % sequence_number

        checkpoint_name = name_base + '.checkpoint'
        checkpoint_path = os.path.join(data_dir, checkpoint_name)
        logger.info("Writing checkpoint to %s", checkpoint_path)

        assert not os.path.exists(checkpoint_path)

        checkpoint = self.serialize()

        fp = fileutil.File(checkpoint_path)
        fp.write_json(
            checkpoint,
            fileutil.FileInfo(filetype='project-checkpoint',
                              version=self.VERSION),
            encoder=JSONEncoder)

        command_log_name = name_base + '.log'
        command_log_path = os.path.join(data_dir, command_log_name)
        command_log_fp = fileutil.MimeLogFile(command_log_path, 'w')

        state_data = {
            'sequence_number': sequence_number,
            'checkpoint': checkpoint_name,
            'log': command_log_name,
        }
        return state_data, command_log_fp

    def dispatch_command(self, obj_id, cmd):
        if self.closed:
            raise RuntimeError("Command %s executed on closed project." % cmd)

        assert self.command_log_fp is not None

        result = super().dispatch_command(obj_id, cmd)

        serialized = json.dumps(
            cmd.serialize(),
            ensure_ascii=False, indent='  ', sort_keys=True, cls=JSONEncoder)
        now = time.time()
        self.command_log_fp.append(
            serialized,
            content_type='application/json',
            encoding='utf-8',
            entry_type=b'C',
            headers={
                'Target': obj_id,
                'Time': time.ctime(now),
                'Timestamp': '%d' % now,
            })

        return result
