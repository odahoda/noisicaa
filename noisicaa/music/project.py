#!/usr/bin/python3

import logging
import os
import os.path
import time
import glob
import json

import portalocker

from noisicaa import core
from noisicaa.audioproc.compose.mix import Mix
from noisicaa import file as fileutil

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
from .score_track import ScoreTrack
from .sheet_property_track import SheetPropertyTrack
from .time import Duration

logger = logging.getLogger(__name__)


class AddSheet(core.Command):
    def __init__(self, name=None):
        super().__init__()
        self.name = name

    def run(self, project):
        assert isinstance(project, Project)

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


class ClearSheet(core.Command):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def run(self, project):
        assert isinstance(project, Project)

        project.get_sheet(self.name).clear()


class DeleteSheet(core.Command):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def run(self, project):
        assert isinstance(project, Project)

        assert len(project.sheets) > 1
        for idx, sheet in enumerate(project.sheets):
            if sheet.name == self.name:
                del project.sheets[idx]
                project.current_sheet = min(
                    project.current_sheet, len(project.sheets) - 1)
                return

        raise ValueError("No sheet %r" % self.name)


class RenameSheet(core.Command):
    def __init__(self, name, new_name):
        super().__init__()
        self.name = name
        self.new_name = new_name

    def run(self, project):
        assert isinstance(project, Project)

        if self.name == self.new_name:
            return

        if self.new_name in [s.name for s in project.sheets]:
            raise ValueError("Sheet %s already exists" % self.new_name)

        sheet = project.get_sheet(self.name)
        sheet.name = self.new_name


class SetCurrentSheet(core.Command):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def run(self, project):
        assert isinstance(project, Project)

        project.current_sheet = project.get_sheet_index(self.name)



class AddTrack(core.Command):
    def __init__(self, track_type):
        super().__init__()
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
        sheet.update_tracks()

        return len(sheet.tracks) - 1


class RemoveTrack(core.Command):
    def __init__(self, track):
        super().__init__()
        self.track = track

    def run(self, sheet):
        assert isinstance(sheet, Sheet)

        del sheet.tracks[self.track]
        sheet.update_tracks()


class MoveTrack(core.Command):
    def __init__(self, track, direction):
        super().__init__()
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
            sheet.update_tracks()

        elif self.direction > 0:
            if track.index == len(sheet.tracks) - 1:
                raise ValueError("Can't move last track down.")
            new_pos = track.index + 1
            del sheet.tracks[track.index]
            sheet.tracks.insert(new_pos, track)
            sheet.update_tracks()

        return track.index


class InsertMeasure(core.Command):
    def __init__(self, tracks, pos):
        super().__init__()
        self.tracks = tracks
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


class RemoveMeasure(core.Command):
    def __init__(self, tracks, pos):
        super().__init__()
        self.tracks = tracks
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


class Sheet(core.StateBase, core.CommandTarget):
    name = core.Property(str, default="Sheet")
    tracks = core.ObjectListProperty(Track)
    property_track = core.ObjectProperty(SheetPropertyTrack)

    def __init__(self, name=None, num_tracks=1, state=None):
        super().__init__()
        self.init_state(state)
        if state is None:
            self.name = name

            self.property_track = SheetPropertyTrack(name="Time")

            for i in range(num_tracks):
                self.tracks.append(ScoreTrack(name="Track %d" % i))

        self.update_tracks()

    @property
    def address(self):
        return self.parent.address + 'sheet:' + self.name

    @property
    def project(self):
        return self.parent

    @property
    def all_tracks(self):
        return [self.property_track] + list(self.tracks)

    def clear(self):
        pass

    def get_bpm(self, measure_idx, tick):  # pylint: disable=unused-argument
        return self.property_track.measures[measure_idx].bpm

    def get_time_signature(self, measure_idx):
        return self.property_track.measures[measure_idx].time_signature

    def create_playback_source(self, pipeline):
        mixer = Mix()
        pipeline.add_node(mixer)
        mixer.setup()
        return mixer

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
                track.update_measures()

            remove_trailing_empty_measures -= 1

        max_length = max(len(track.measures) for track in self.all_tracks)

        for track in self.all_tracks:
            while len(track.measures) < max_length:
                track.append_measure()
                track.update_measures()

    def update_tracks(self):
        # This sure is very inefficient. Do we care?
        for idx, track in enumerate(self.tracks):
            track.index = idx

    def get_sub_target(self, name):
        if name.startswith('track:'):
            return self.tracks[int(name[6:])]

        if name == 'property_track':
            return self.property_track

        return super().get_sub_target(name)


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


class Project(core.StateBase, core.CommandDispatcher):
    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    sheets = core.ObjectListProperty(cls=Sheet)
    current_sheet = core.Property(int, default=0)

    def __init__(self, state=None):
        super().__init__()
        self.init_state(state)
        if state is None:
            self.sheets.append(Sheet(name="Sheet 1"))

        self.file_lock = None
        self.header_data = None
        self.path = None
        self.data_dir = None

        self.address = '/'
        self.set_root()

        self.changed_since_last_checkpoint = False

    @property
    def name(self):
        if self.path is None:
            return '*New Project*'
        return os.path.basename(self.path)

    @property
    def closed(self):
        return self.path is None

    @property
    def has_unsaved_changes(self):
        return self.changed_since_last_checkpoint

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

        checkpoints = []
        for cpath in glob.glob(os.path.join(data_dir, 'checkpoint.*')):
            timestamp = int(os.path.basename(cpath).split('.')[1])
            checkpoints.append((timestamp, cpath))
        checkpoints.sort(reverse=True)
        if len(checkpoints) > 0:
            checkpoint_path = checkpoints[0][1]
            self.read_checkpoint(checkpoint_path)

        self.file_lock = file_lock
        self.header_data = data
        self.path = path
        self.data_dir = data_dir

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

        file_lock = self.acquire_file_lock(os.path.join(data_dir, "lock"))

        self.file_lock = file_lock
        self.path = path
        self.data_dir = data_dir
        self.header_data = header_data
        self.changed_since_last_checkpoint = False

    def close(self):
        if self.file_lock is not None:
            self.release_file_lock(self.file_lock)

        self.file_lock = None
        self.header_data = None
        self.path = None
        self.data_dir = None

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

        self.changed_since_last_checkpoint = False

    def write_checkpoint(self):
        assert self.path is not None

        path = os.path.join(
            self.data_dir, 'checkpoint.%d' % time.time())
        logger.info("Writing checkpoint to %s", path)

        assert not os.path.exists(path)

        checkpoint = self.serialize()

        fp = fileutil.File(path)
        fp.write_json(
            checkpoint,
            fileutil.FileInfo(filetype='project-checkpoint',
                              version=self.VERSION),
            encoder=JSONEncoder)

        self.changed_since_last_checkpoint = False

        return path

    def get_current_sheet(self):
        return self.sheets[self.current_sheet]

    def get_sheet(self, name):
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        raise ValueError("No sheet %r" % name)

    def get_sheet_index(self, name):
        for idx, sheet in enumerate(self.sheets):
            if sheet.name == name:
                return idx
        raise ValueError("No sheet %r" % name)

    def get_sub_target(self, name):
        if name.startswith('sheet:'):
            sheet_name = name[6:]
            for sheet in self.sheets:
                if sheet.name == sheet_name:
                    return sheet

        return super().get_sub_target(name)

    def dispatch_command(self, target, cmd):
        if self.closed:
            raise RuntimeError("Command %s executed on closed project." % cmd)

        result = super().dispatch_command(target, cmd)
        self.changed_since_last_checkpoint = True
        logger.info("Executed command %s on %s", cmd, target)
        return result
