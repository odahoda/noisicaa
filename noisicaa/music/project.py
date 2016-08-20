#!/usr/bin/python3

import email.parser
import email.policy
import email.message
import logging
import time
import json

from noisicaa import core
from noisicaa.core import storage

from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from .time_signature import TimeSignature
from .score_track import ScoreTrack, Note
from .time import Duration
from . import model
from . import state
from . import commands
from . import instruments
from . import sheet
from . import misc

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
        s = sheet.Sheet(name)
        project.sheets.append(s)

        s.add_to_pipeline()

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
                sheet.remove_from_pipeline()
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
        if isinstance(obj, misc.Pos2F):
            return {'__type__': 'Pos2F',
                    'value': [obj.x, obj.y]}
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
        if objtype == 'Pos2F':
            return misc.Pos2F(*obj['value'])
        return obj


class BaseProject(model.Project, state.RootMixin, state.StateBase):
    SERIALIZED_CLASS_NAME = 'Project'

    def __init__(self, state=None):
        self.listeners = core.CallbackRegistry()

        super().__init__(state)
        if state is None:
            self.metadata = Metadata()

    def dispatch_command(self, obj_id, cmd):
        obj = self.get_object(obj_id)
        result = cmd.apply(obj)
        logger.info(
            "Executed command %s on %s (%d operations)",
            cmd, obj_id, len(cmd.log.ops))
        return result

    @classmethod
    def make_demo(cls):
        project = cls()
        s = sheet.Sheet(name="Demo Sheet", num_tracks=0)
        project.sheets.append(s)

        while len(s.property_track.measures) < 5:
            s.property_track.append_measure()

        for m in s.property_track.measures:
            m.bpm = 140

        instr1 = instruments.SoundFontInstrument(
            name="Flute",
            path='/usr/share/sounds/sf2/FluidR3_GM.sf2', bank=0, preset=73)
        track1 = ScoreTrack(name="Track 1", instrument=instr1, num_measures=5)
        s.master_group.tracks.append(track1)

        instr2 = instruments.SoundFontInstrument(
            name="Yamaha Grand Piano",
            path='/usr/share/sounds/sf2/FluidR3_GM.sf2', bank=0, preset=0)
        track2 = ScoreTrack(name="Track 2", instrument=instr2, num_measures=5)
        s.master_group.tracks.append(track2)

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

    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        self.storage = None

    @property
    def closed(self):
        return self.storage is None

    @property
    def path(self):
        if self.storage:
            return self.storage.path
        return None

    def open(self, path):
        assert self.storage is None

        self.storage = storage.ProjectStorage()
        self.storage.open(path)

        checkpoint_number, actions = self.storage.get_restore_info()

        serialized_checkpoint = self.storage.get_checkpoint(
            checkpoint_number)

        self.load_from_checkpoint(serialized_checkpoint)
        for action, log_number in actions:
            cmd_data = self.storage.get_log_entry(log_number)
            cmd, obj_id = self.deserialize_command(cmd_data)
            logger.info(
                "Replay action %s of command %s on %s (%d operations)",
                action, cmd, obj_id, len(cmd.log.ops))
            obj = self.get_object(obj_id)

            if action == storage.ACTION_FORWARD:
                cmd.redo(obj)
            elif action == storage.ACTION_BACKWARD:
                cmd.undo(obj)
            else:
                raise ValueError("Unsupported action %s" % action)

    def create(self, path):
        assert self.storage is None

        self.storage = storage.ProjectStorage.create(path)

        # Write initial checkpoint of an empty project.
        self.create_checkpoint()

    def close(self):
        if self.storage is not None:
            self.storage.close()
            self.storage = None

        self.listeners.clear()
        self.reset_state()

    def load_from_checkpoint(self, checkpoint_data):
        parser = email.parser.BytesParser()
        message = parser.parsebytes(checkpoint_data)

        version = int(message['Version'])
        if version not in self.SUPPORTED_VERSIONS:
            raise storage.UnsupportedFileVersionError()

        if message.get_content_type() != 'application/json':
            raise storage.CorruptedProjectError(
                "Unexpected content type %s" % message.get_content_type())

        serialized_checkpoint = message.get_payload()

        checkpoint = json.loads(serialized_checkpoint, cls=JSONDecoder)

        self.deserialize(checkpoint)
        self.init_references()

        def validate_node(root, parent, node):
            assert node.parent is parent, (node.parent, parent)
            assert node.root is root, (node.root, root)

            for c in node.list_children():
                validate_node(root, node, c)

        validate_node(self, None, self)

    def create_checkpoint(self):
        policy = email.policy.compat32.clone(
            linesep='\n',
            max_line_length=0,
            cte_type='8bit',
            raise_on_defect=True)
        message = email.message.Message(policy)

        message['Version'] = str(self.VERSION)
        message['Content-Type'] = 'application/json; charset=utf-8'

        checkpoint = json.dumps(
            self.serialize(),
            ensure_ascii=False, indent='  ', sort_keys=True,
            cls=JSONEncoder)
        serialized_checkpoint = checkpoint.encode('utf-8')
        message.set_payload(serialized_checkpoint)

        checkpoint_data = message.as_bytes()
        self.storage.add_checkpoint(checkpoint_data)

    def serialize_command(self, cmd, target_id, now):
        serialized = json.dumps(
            cmd.serialize(),
            ensure_ascii=False, indent='  ', sort_keys=True,
            cls=JSONEncoder)

        policy = email.policy.compat32.clone(
            linesep='\n',
            max_line_length=0,
            cte_type='8bit',
            raise_on_defect=True)
        message = email.message.Message(policy)
        message['Version'] = str(self.VERSION)
        message['Content-Type'] = 'application/json; charset=utf-8'
        message['Target'] = target_id
        message['Time'] = time.ctime(now)
        message['Timestamp'] = '%d' % now
        message.set_payload(serialized.encode('utf-8'))

        return message.as_bytes()

    def deserialize_command(self, cmd_data):
        parser = email.parser.BytesParser()
        message = parser.parsebytes(cmd_data)

        target_id = message['Target']
        cmd_state = json.loads(message.get_payload(), cls=JSONDecoder)
        cmd = commands.Command.create_from_state(cmd_state)

        return cmd, target_id

    def dispatch_command(self, obj_id, cmd):
        if self.closed:
            raise RuntimeError(
                "Command %s executed on closed project." % cmd)

        now = time.time()
        result = super().dispatch_command(obj_id, cmd)

        self.storage.append_log_entry(
            self.serialize_command(cmd, obj_id, now))

        if self.storage.logs_since_last_checkpoint > 1000:
            self.create_checkpoint()

        return result

    def undo(self):
        if self.closed:
            raise RuntimeError("Undo executed on closed project.")

        if self.storage.can_undo:
            action, cmd_data = self.storage.get_log_entry_to_undo()
            cmd, obj_id = self.deserialize_command(cmd_data)
            logger.info(
                "Undo command %s on %s (%d operations)",
                cmd, obj_id, len(cmd.log.ops))
            obj = self.get_object(obj_id)

            if action == storage.ACTION_FORWARD:
                cmd.redo(obj)
            elif action == storage.ACTION_BACKWARD:
                cmd.undo(obj)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.storage.undo()

    def redo(self):
        if self.closed:
            raise RuntimeError("Redo executed on closed project.")

        if self.storage.can_redo:
            action, cmd_data = self.storage.get_log_entry_to_redo()
            cmd, obj_id = self.deserialize_command(cmd_data)
            logger.info(
                "Redo command %s on %s (%d operations)",
                cmd, obj_id, len(cmd.log.ops))
            obj = self.get_object(obj_id)

            if action == storage.ACTION_FORWARD:
                cmd.redo(obj)
            elif action == storage.ACTION_BACKWARD:
                cmd.undo(obj)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.storage.redo()
