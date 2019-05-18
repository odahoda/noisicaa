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

import collections
import enum
import hashlib
import logging
import os
import os.path
import time
import struct
from typing import cast, Dict, List, Set, Tuple, IO

from mypy_extensions import TypedDict
import portalocker

from . import fileutil
from . import storage_pb2

logger = logging.getLogger(__name__)


class Error(Exception):
    pass

class FileOpenError(Error):
    pass

class UnsupportedFileVersionError(Error):
    pass

class CorruptedProjectError(Error):
    pass


HeaderData = TypedDict('HeaderData', {'data_dir': str, 'created': int})

LogEntry = bytes
Checkpoint = bytes
HistoryEntry = Tuple[bytes, int, int, int]
CheckpointIndexEntry = Tuple[int, int]


class Action(enum.Enum):
    FORWARD = b'f'
    BACKWARD = b'b'

ACTION_FORWARD = Action.FORWARD
ACTION_BACKWARD = Action.BACKWARD

def _reverse_action(action: bytes) -> bytes:
    if action == ACTION_BACKWARD.value:
        return ACTION_FORWARD.value
    return ACTION_BACKWARD.value


class ProjectStorage(object):
    MAGIC = b'NOISICAA\n'

    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    def __init__(self) -> None:
        self.path = None  # type: str
        self.data_dir = None  # type: str
        self.header_data = None  # type: HeaderData
        self.file_lock = None  # type: IO
        self.log_index_fp = None  # type: IO[bytes]
        self.log_history_fp = None  # type: IO[bytes]
        self.checkpoint_index_fp = None  # type: IO[bytes]

        self.next_log_number = None  # type: int
        self.log_file_number = 0
        self.log_fp = None  # type: IO[bytes]
        self.log_fp_map = {}  # type: Dict[int, IO]
        self.log_index_formatter = struct.Struct('>QQ')
        self.log_index = None # type: bytearray

        self.log_history_formatter = struct.Struct('>cQQQ')
        self.next_sequence_number = None  # type: int
        self.undo_count = None  # type: int
        self.redo_count = None  # type: int
        self.log_history = None  # type: bytearray

        self.next_checkpoint_number = None  # type: int
        self.checkpoint_index_formatter = struct.Struct('>QQ')
        self.checkpoint_index = None  # type: bytearray

        self.log_entry_cache = collections.OrderedDict()  # type: collections.OrderedDict[int, LogEntry]
        self.log_entry_cache_size = 20

        self.written_log_number = None  # type: int
        self.written_sequence_number = None  # type: int

    def open(self, path: str) -> None:
        assert self.path is None

        self.path = os.path.abspath(path)
        logger.info("Opening project at %s", self.path)

        try:
            fp = fileutil.File(path)
            file_info, self.header_data = fp.read_json()
        except fileutil.Error as exc:
            raise FileOpenError(str(exc))

        if file_info.filetype != 'project-header':
            raise FileOpenError("Not a project file")

        if file_info.version not in self.SUPPORTED_VERSIONS:
            raise UnsupportedFileVersionError()

        self.data_dir = os.path.join(
            os.path.dirname(self.path), self.header_data['data_dir'])
        if not os.path.isdir(self.data_dir):
            raise CorruptedProjectError(
                "Directory %s missing" % self.data_dir)

        self.file_lock = self.acquire_file_lock(
            os.path.join(self.data_dir, "lock"))

        log_path = os.path.join(self.data_dir, 'log.%06d' % self.log_file_number)
        if os.path.exists(log_path):
            mode = 'a+b'
        else:
            mode = 'w+b'
        self.log_fp = open(log_path, mode=mode, buffering=0)

        self.log_index_fp = open(
            os.path.join(self.data_dir, 'log.index'),
            mode='r+b', buffering=0)
        self.log_index = bytearray(self.log_index_fp.read())
        self.next_log_number = len(self.log_index) // self.log_index_formatter.size
        if len(self.log_index) != self.next_log_number * self.log_index_formatter.size:
            raise CorruptedProjectError("Malformed log.index file.")
        self.written_log_number = self.next_log_number - 1

        self.log_history_fp = open(
            os.path.join(self.data_dir, 'log.history'),
            mode='r+b', buffering=0)
        self.log_history = bytearray(self.log_history_fp.read())
        self.next_sequence_number = len(self.log_history) // self.log_history_formatter.size
        if len(self.log_history) != self.next_sequence_number * self.log_history_formatter.size:
            raise CorruptedProjectError("Malformed log.history file.")
        self.written_sequence_number = self.next_sequence_number - 1

        if self.written_sequence_number >= 0:
            self.undo_count, self.redo_count = self._get_history_entry(
                self.written_sequence_number)[2:4]
        else:
            self.undo_count = 0
            self.redo_count = 0

        self.checkpoint_index_fp = open(
            os.path.join(self.data_dir, 'checkpoint.index'),
            mode='r+b', buffering=0)
        self.checkpoint_index = bytearray(self.checkpoint_index_fp.read())
        self.next_checkpoint_number = (
            len(self.checkpoint_index) // self.checkpoint_index_formatter.size)
        if len(self.checkpoint_index) != (
                self.next_checkpoint_number * self.checkpoint_index_formatter.size):
            raise CorruptedProjectError("Malformed checkpoint.index file.")

    def get_restore_info(self) -> Tuple[int, List[Tuple[Action, int]]]:
        assert self.next_checkpoint_number > 0

        seq_number, checkpoint_number = self._get_checkpoint_entry(
            self.next_checkpoint_number - 1)

        actions = []
        for snum in range(seq_number, self.next_sequence_number):
            action, log_number = self._get_history_entry(snum)[0:2]
            actions.append((Action(action), log_number))

        return checkpoint_number, actions

    @classmethod
    def create(cls, path: str) -> 'ProjectStorage':
        header_data = {
            'created': int(time.time()),
            'data_dir': os.path.splitext(os.path.basename(path))[0] + '.data',
        }  # type: HeaderData
        data_dir = os.path.join(os.path.dirname(path), header_data['data_dir'])

        os.mkdir(data_dir)

        for fname in ('lock', 'log.index', 'log.history',
                      'checkpoint.index'):
            open(os.path.join(data_dir, fname), 'wb').close()

        fp = fileutil.File(path)
        fp.write_json(
            header_data,
            fileutil.FileInfo(
                filetype='project-header',
                version=cls.VERSION))

        # There's a short, but probably irrelevant race here: Some other
        # process could open and lock our freshly created project,
        # causing the open call here to fail. Let's not care about that.
        project_storage = cls()
        project_storage.open(path)
        return project_storage

    def close(self) -> None:
        assert self.path is not None, "Project already closed."
        self.path = None

        if self.log_index_fp is not None:
            self.log_index_fp.close()
            self.log_index_fp = None

        if self.log_history_fp is not None:
            self.log_history_fp.close()
            self.log_history_fp = None

        if self.log_fp is not None:
            self.log_fp.close()
            self.log_fp = None

        for log_fp in self.log_fp_map.values():
            log_fp.close()
        self.log_fp_map.clear()

        if self.checkpoint_index_fp is not None:
            self.checkpoint_index_fp.close()
            self.checkpoint_index_fp = None

        self.release_file_lock(self.file_lock)
        self.file_lock = None

    @classmethod
    def acquire_file_lock(cls, lock_path: str) -> IO:
        logger.info("Aquire file lock (%s).", lock_path)
        lock_fp = open(lock_path, 'wb')
        portalocker.lock(
            lock_fp, portalocker.LOCK_EX | portalocker.LOCK_NB)
        return lock_fp

    @classmethod
    def release_file_lock(cls, lock_fp: IO) -> None:
        logger.info("Releasing file lock.")
        lock_fp.close()

    def _write_log(
            self, seq_number: int, history_entry: HistoryEntry, log_entry: LogEntry) -> None:
        log_number = history_entry[1]

        logger.info("Writing log entry #%d...", seq_number)

        if log_entry is not None:
            offset = self.log_fp.tell()

            self.log_fp.write(struct.pack('>Q', len(log_entry)))
            self.log_fp.write(log_entry)
            self.log_fp.flush()

            packed_index_entry = self.log_index_formatter.pack(
                self.log_file_number, offset)
            self.log_index_fp.write(packed_index_entry)
            self.log_index_fp.flush()

        packed_history_entry = self.log_history_formatter.pack(
            *history_entry)
        self.log_history_fp.write(packed_history_entry)
        self.log_history_fp.flush()

        assert seq_number > self.written_sequence_number
        self.written_sequence_number = seq_number

        if log_entry is not None:
            self.log_index += packed_index_entry
            assert log_number > self.written_log_number
            self.written_log_number = log_number

    def _write_checkpoint(
            self, seq_number: int, checkpoint_number: int, checkpoint: Checkpoint) -> None:
        checkpoint_path = os.path.join(
            self.data_dir,
            'checkpoint.%06d' % checkpoint_number)
        logger.info("Writing checkpoint %s...", checkpoint_path)
        with open(checkpoint_path, mode='wb', buffering=0) as fp:
            header = storage_pb2.FileHeader()
            header.type = 'checkpoint'
            header.version = self.VERSION
            header.create_timestamp = int(time.time())
            header.size = len(checkpoint)
            header.checksum_type = storage_pb2.FileHeader.MD5
            header.checksum = hashlib.md5(checkpoint).digest()
            self._write_file_header(fp, header)

            fp.write(checkpoint)

        packed_index_entry = self.checkpoint_index_formatter.pack(
            seq_number, checkpoint_number)
        self.checkpoint_index_fp.write(packed_index_entry)
        self.checkpoint_index_fp.flush()

    def _write_file_header(self, fp: IO[bytes], header: storage_pb2.FileHeader) -> None:
        fp.write(self.MAGIC)
        header_serialized = header.SerializeToString()
        fp.write(struct.pack('>L', len(header_serialized)))
        fp.write(header_serialized)

    def _read_file_header(self, fp: IO[bytes]) -> storage_pb2.FileHeader:
        magic = fp.read(len(self.MAGIC))
        if magic != self.MAGIC:
            raise CorruptedProjectError("Invalid magic.")

        header_size_b = fp.read(4)
        if len(header_size_b) < 4:
            raise CorruptedProjectError("Truncated file.")
        header_size = struct.unpack('>L', header_size_b)[0]
        header_serialized = fp.read(header_size)
        if len(header_serialized) != header_size:
            raise CorruptedProjectError("Truncated file.")

        header = storage_pb2.FileHeader()
        header.MergeFromString(header_serialized)

        return header

    def _get_history_entry(self, seq_number: int) -> HistoryEntry:
        size = self.log_history_formatter.size
        offset = seq_number * size
        packed_entry = self.log_history[offset:offset+size]
        return cast(HistoryEntry, self.log_history_formatter.unpack(packed_entry))

    def _add_history_entry(self, entry: HistoryEntry) -> None:
        packed_entry = self.log_history_formatter.pack(*entry)
        self.log_history += packed_entry

    def _get_log_fp(self, file_number: int) -> IO[bytes]:
        try:
            return self.log_fp_map[file_number]
        except KeyError:
            log_fp = open(
                os.path.join(
                    self.data_dir,
                    'log.%06d' % file_number),
                mode='r+b', buffering=0)
            self.log_fp_map[self.log_file_number] = log_fp
            return log_fp

    def _read_log_entry(self, log_number: int) -> LogEntry:
        size = self.log_index_formatter.size
        offset = log_number * size
        packed_index_entry = self.log_index[offset:offset+size]
        file_number, file_offset = self.log_index_formatter.unpack(
            packed_index_entry)

        log_fp = self._get_log_fp(file_number)
        log_fp.seek(file_offset, os.SEEK_SET)

        entry_len, = struct.unpack(
            '>Q', log_fp.read(struct.calcsize('>Q')))
        return log_fp.read(entry_len)

    def get_log_entry(self, log_number: int) -> LogEntry:
        try:
            entry = self.log_entry_cache[log_number]
            self.log_entry_cache.move_to_end(log_number)  # pylint: disable=no-member
        except KeyError:
            entry = self._read_log_entry(log_number)
            self._add_log_entry(log_number, entry)
        return entry

    def _add_log_entry(self, log_number: int, entry: LogEntry) -> None:
        self.log_entry_cache[log_number] = entry
        self.flush_cache(self.log_entry_cache_size)

    def _get_checkpoint_entry(self, checkpoint_number: int) -> CheckpointIndexEntry:
        size = self.checkpoint_index_formatter.size
        offset = checkpoint_number * size
        packed_entry = self.checkpoint_index[offset:offset+size]
        return cast(CheckpointIndexEntry, self.checkpoint_index_formatter.unpack(packed_entry))

    def flush_cache(self, cache_size: int) -> None:
        entries_to_drop = len(self.log_entry_cache) - cache_size
        if entries_to_drop > 0:
            dropped_entries = set()  # type: Set[int]
            for ln in self.log_entry_cache.keys():
                if len(dropped_entries) >= entries_to_drop:
                    break
                if ln > self.written_log_number:
                    continue
                dropped_entries.add(ln)

            for ln in dropped_entries:
                del self.log_entry_cache[ln]

    def append_log_entry(self, entry: LogEntry) -> None:
        assert self.path is not None, "Project already closed."

        assert self.next_log_number not in self.log_entry_cache

        self.undo_count = 0
        self.redo_count = 0

        history_entry = (
            ACTION_FORWARD.value, self.next_log_number,
            self.undo_count, self.redo_count)

        self._add_history_entry(history_entry)
        self._add_log_entry(self.next_log_number, entry)
        self._write_log(self.next_sequence_number, history_entry, entry)

        self.next_log_number += 1
        self.next_sequence_number += 1

    @property
    def can_undo(self) -> bool:
        return self.next_sequence_number - 2 * self.undo_count > 0

    @property
    def can_redo(self) -> bool:
        return self.undo_count > self.redo_count

    def get_log_entry_to_undo(self) -> Tuple[Action, LogEntry]:
        assert self.can_undo

        entry_to_undo = self.next_sequence_number - 2 * self.undo_count - 1

        action, log_number = self._get_history_entry(entry_to_undo)[0:2]
        return Action(_reverse_action(action)), self.get_log_entry(log_number)

    def get_log_entry_to_redo(self) -> Tuple[Action, LogEntry]:
        assert self.can_redo

        entry_to_redo = self.next_sequence_number - 2 * self.undo_count

        action, log_number = self._get_history_entry(entry_to_redo)[0:2]
        return Action(action), self.get_log_entry(log_number)

    def undo(self) -> None:
        assert self.path is not None, "Project already closed."
        assert self.can_undo

        entry_to_undo = self.next_sequence_number - 2 * self.undo_count - 1
        action, log_number = self._get_history_entry(entry_to_undo)[0:2]

        self.undo_count += 1
        history_entry = (_reverse_action(action), log_number, self.undo_count, self.redo_count)
        self._add_history_entry(history_entry)

        self._write_log(self.next_sequence_number, history_entry, None)

        self.next_sequence_number += 1

    def redo(self) -> None:
        assert self.path is not None, "Project already closed."
        assert self.can_redo

        entry_to_redo = self.next_sequence_number - 2 * self.undo_count
        action, log_number = self._get_history_entry(entry_to_redo)[0:2]

        self.redo_count += 1
        history_entry = (action, log_number, self.undo_count, self.redo_count)
        self._add_history_entry(history_entry)

        self._write_log(self.next_sequence_number, history_entry, None)

        self.next_sequence_number += 1

    @property
    def logs_since_last_checkpoint(self) -> int:
        if self.next_checkpoint_number == 0:
            return self.next_sequence_number
        seq_number, _ = self._get_checkpoint_entry(self.next_checkpoint_number - 1)
        return self.next_sequence_number - seq_number

    def add_checkpoint(self, checkpoint: Checkpoint) -> None:
        self._write_checkpoint(
            self.next_sequence_number, self.next_checkpoint_number, checkpoint)

        packed_index_entry = self.checkpoint_index_formatter.pack(
            self.next_sequence_number, self.next_checkpoint_number)
        self.checkpoint_index += packed_index_entry
        self.next_checkpoint_number += 1

    def get_checkpoint(self, checkpoint_number: int) -> Checkpoint:
        checkpoint_number = self._get_checkpoint_entry(checkpoint_number)[1]

        checkpoint_path = os.path.join(
            self.data_dir,
            'checkpoint.%06d' % checkpoint_number)
        logger.info("Reading checkpoint %s...", checkpoint_path)
        with open(checkpoint_path, mode='rb') as fp:
            header = self._read_file_header(fp)
            if header.type != 'checkpoint':
                raise CorruptedProjectError("Not a checkpoint file")
            if header.version not in self.SUPPORTED_VERSIONS:
                raise UnsupportedFileVersionError("File version %d not supported" % header.version)

            checkpoint = fp.read(header.size)
            if len(checkpoint) != header.size:
                raise CorruptedProjectError("Truncated file")

            if header.checksum_type == storage_pb2.FileHeader.MD5:
                checksum = hashlib.md5(checkpoint).digest()
                if checksum != header.checksum:
                    raise CorruptedProjectError("Checksum mismatch")
            else:
                raise UnsupportedFileVersionError(
                    "Checksum type %d not supported" % header.checksum_type)

            return checkpoint
