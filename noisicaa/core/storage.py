#!/usr/bin/python3

import collections
import logging
import os
import os.path
import time
import struct
import queue
import threading

import portalocker

from . import fileutil


logger = logging.getLogger(__name__)


class Error(Exception):
    pass

class FileOpenError(Error):
    pass

class UnsupportedFileVersionError(Error):
    pass

class CorruptedProjectError(Error):
    pass


ACTION_FORWARD = b'f'
ACTION_BACKWARD = b'b'

def _reverse_action(action):
    assert action in (ACTION_FORWARD, ACTION_BACKWARD)
    if action == ACTION_BACKWARD:
        return ACTION_FORWARD
    return ACTION_BACKWARD


class ProjectStorage(object):
    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    def __init__(self):
        self.path = None
        self.data_dir = None
        self.header_data = None
        self.file_lock = None
        self.log_index_fp = None
        self.log_history_fp = None
        self.checkpoint_index_fp = None

        self.next_log_number = None
        self.log_file_number = 0
        self.log_fp_map = {}
        self.log_index_formatter = struct.Struct('>QQ')
        self.log_index = None

        self.log_history_formatter = struct.Struct('>cQQQ')
        self.next_sequence_number = None
        self.undo_count = None
        self.redo_count = None
        self.log_history = None

        self.next_checkpoint_number = None
        self.checkpoint_index_formatter = struct.Struct('>QQ')
        self.checkpoint_index = None

        self.cache_lock = threading.RLock()
        self.log_entry_cache = collections.OrderedDict()
        self.log_entry_cache_size = 20

        self.write_queue = queue.Queue()
        self.writer_thread = threading.Thread(target=self._writer_main)
        self.written_log_number = None
        self.written_sequence_number = None

    def open(self, path):
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
            _, _, self.undo_count, self.redo_count = self._get_history_entry(self.written_sequence_number)
        else:
            self.undo_count = 0
            self.redo_count = 0

        self.checkpoint_index_fp = open(
            os.path.join(self.data_dir, 'checkpoint.index'),
            mode='r+b', buffering=0)
        self.checkpoint_index = bytearray(self.checkpoint_index_fp.read())
        self.next_checkpoint_number = len(self.checkpoint_index) // self.checkpoint_index_formatter.size
        if len(self.checkpoint_index) != self.next_checkpoint_number * self.checkpoint_index_formatter.size:
            raise CorruptedProjectError("Malformed checkpoint.index file.")

        self.writer_thread.start()

    def get_restore_info(self):
        assert self.next_checkpoint_number > 0

        seq_number, checkpoint_number = self._get_checkpoint_entry(
            self.next_checkpoint_number - 1)

        actions = []
        for snum in range(seq_number, self.next_sequence_number):
            action, log_number, _, _ = self._get_history_entry(snum)
            actions.append((action, log_number))

        return checkpoint_number, actions

    @classmethod
    def create(cls, path):
        header_data = {
            'created': int(time.time()),
            'data_dir': os.path.splitext(
                os.path.basename(path))[0] + '.data',
        }
        data_dir = os.path.join(
            os.path.dirname(path), header_data['data_dir'])

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

    def close(self):
        assert self.path is not None, "Project already closed."
        self.path = None

        if self.writer_thread is not None:
            self.write_queue.put(('STOP', None))
            self.writer_thread.join()
            self.writer_thread = None

        if self.log_index_fp is not None:
            self.log_index_fp.close()
            self.log_index_fp = None

        if self.log_history_fp is not None:
            self.log_history_fp.close()
            self.log_history_fp = None

        for log_fp in self.log_fp_map.values():
            log_fp.close()
        self.log_fp_map.clear()

        if self.checkpoint_index_fp is not None:
            self.checkpoint_index_fp.close()
            self.checkpoint_index_fp = None

        self.release_file_lock(self.file_lock)
        self.file_lock = None

    @classmethod
    def acquire_file_lock(cls, lock_path):
        logger.info("Aquire file lock (%s).", lock_path)
        lock_fp = open(lock_path, 'wb')
        portalocker.lock(
            lock_fp, portalocker.LOCK_EX | portalocker.LOCK_NB)
        return lock_fp

    @classmethod
    def release_file_lock(cls, lock_fp):
        logger.info("Releasing file lock.")
        lock_fp.close()

    def _schedule_log_write(self, seq_number, history_entry, log_entry):
        assert self.writer_thread.is_alive()
        self.write_queue.put(
            ('LOG', (seq_number, history_entry, log_entry)))

    def _schedule_checkpoint_write(
            self, seq_number, checkpoint_number, checkpoint):
        assert self.writer_thread.is_alive()
        self.write_queue.put(
            ('CHECKPOINT', (seq_number, checkpoint_number, checkpoint)))

    def _writer_main(self):
        logger.info("Log writer thread started.")

        log_path = os.path.join(
            self.data_dir,
            'log.%06d' % self.log_file_number)

        if os.path.exists(log_path):
            mode = 'a+b'
        else:
            mode = 'w+b'

        with open(log_path, mode=mode, buffering=0) as log_fp:
            while True:
                cmd, arg = self.write_queue.get()
                if cmd == 'STOP':
                    break
                elif cmd == 'FLUSH':
                    arg.set()
                elif cmd == 'PAUSE':
                    arg.wait()
                elif cmd == 'LOG':
                    seq_number, history_entry, log_entry = arg
                    action, log_number, _, _ = history_entry

                    logger.info("Writing log entry #%d...", seq_number)

                    if log_entry is not None:
                        offset = log_fp.tell()

                        log_fp.write(struct.pack('>Q', len(log_entry)))
                        log_fp.write(log_entry)
                        log_fp.flush()

                        packed_index_entry = self.log_index_formatter.pack(
                            self.log_file_number, offset)
                        self.log_index_fp.write(packed_index_entry)
                        self.log_index_fp.flush()

                    packed_history_entry = self.log_history_formatter.pack(
                        *history_entry)
                    self.log_history_fp.write(packed_history_entry)
                    self.log_history_fp.flush()

                    with self.cache_lock:
                        assert seq_number > self.written_sequence_number
                        self.written_sequence_number = seq_number

                        if log_entry is not None:
                            self.log_index += packed_index_entry
                            assert log_number > self.written_log_number
                            self.written_log_number = log_number
                elif cmd == 'CHECKPOINT':
                    seq_number, checkpoint_number, checkpoint = arg

                    checkpoint_path = os.path.join(
                        self.data_dir,
                        'checkpoint.%06d' % checkpoint_number)
                    logger.info("Writing checkpoint %s...", checkpoint_path)
                    with open(checkpoint_path, mode='wb', buffering=0) as fp:
                        fp.write(checkpoint)

                    packed_index_entry = self.checkpoint_index_formatter.pack(
                        seq_number, checkpoint_number)
                    self.checkpoint_index_fp.write(packed_index_entry)
                    self.checkpoint_index_fp.flush()

                else:  # pragma: no coverage
                    raise ValueError("Invalud command %r", cmd)

        logger.info("Log writer thread finished.")

    def _get_history_entry(self, seq_number):
        size = self.log_history_formatter.size
        offset = seq_number * size
        packed_entry = self.log_history[offset:offset+size]
        return self.log_history_formatter.unpack(packed_entry)

    def _add_history_entry(self, entry):
        packed_entry = self.log_history_formatter.pack(*entry)
        self.log_history += packed_entry

    def _get_log_fp(self, file_number,):
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

    def _read_log_entry(self, log_number):
        with self.cache_lock:
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

    def get_log_entry(self, log_number):
        try:
            entry = self.log_entry_cache[log_number]
            self.log_entry_cache.move_to_end(log_number)
        except KeyError:
            entry = self._read_log_entry(log_number)
            self._add_log_entry(log_number, entry)
        return entry

    def _add_log_entry(self, log_number, entry):
        with self.cache_lock:
            self.log_entry_cache[log_number] = entry
            self.flush_cache(self.log_entry_cache_size)

    def _get_checkpoint_entry(self, checkpoint_number):
        size = self.checkpoint_index_formatter.size
        offset = checkpoint_number * size
        packed_entry = self.checkpoint_index[offset:offset+size]
        return self.checkpoint_index_formatter.unpack(packed_entry)

    def flush_cache(self, cache_size):
        with self.cache_lock:
            entries_to_drop = len(self.log_entry_cache) - cache_size
            if entries_to_drop > 0:
                dropped_entries = set()
                for ln in self.log_entry_cache.keys():
                    if len(dropped_entries) >= entries_to_drop:
                        break
                    if ln > self.written_log_number:
                        continue
                    dropped_entries.add(ln)

                for ln in dropped_entries:
                    del self.log_entry_cache[ln]

    def flush(self):
        flushed = threading.Event()
        self.write_queue.put(('FLUSH', flushed))
        flushed.wait()

    def pause(self):
        evt = threading.Event()
        self.write_queue.put(('PAUSE', evt))
        return evt

    def append_log_entry(self, entry):
        assert self.path is not None, "Project already closed."

        with self.cache_lock:
            assert self.next_log_number not in self.log_entry_cache

            self.undo_count = 0
            self.redo_count = 0

            history_entry = (
                ACTION_FORWARD, self.next_log_number,
                self.undo_count, self.redo_count)

            self._add_history_entry(history_entry)
            self._add_log_entry(self.next_log_number, entry)

            self._schedule_log_write(
                self.next_sequence_number, history_entry, entry)

            self.next_log_number += 1
            self.next_sequence_number += 1

    @property
    def can_undo(self):
        return self.next_sequence_number - 2 * self.undo_count > 0

    @property
    def can_redo(self):
        return self.undo_count > self.redo_count

    def get_log_entry_to_undo(self):
        assert self.can_undo

        entry_to_undo = (
            self.next_sequence_number - 2 * self.undo_count - 1)

        action, log_number, _, _ = (
            self._get_history_entry(entry_to_undo))
        return _reverse_action(action), self.get_log_entry(log_number)

    def get_log_entry_to_redo(self):
        assert self.can_redo

        entry_to_redo = self.next_sequence_number - 2 * self.undo_count

        action, log_number, _, _ = (
            self._get_history_entry(entry_to_redo))
        return action, self.get_log_entry(log_number)

    def undo(self):
        assert self.path is not None, "Project already closed."
        assert self.can_undo

        entry_to_undo = (
            self.next_sequence_number - 2 * self.undo_count - 1)

        with self.cache_lock:
            action, log_number, _, _ = self._get_history_entry(
                entry_to_undo)

            self.undo_count += 1
            history_entry = (
                _reverse_action(action), log_number,
                self.undo_count, self.redo_count)

            self._add_history_entry(history_entry)

            self._schedule_log_write(
                self.next_sequence_number, history_entry, None)

            self.next_sequence_number += 1

    def redo(self):
        assert self.path is not None, "Project already closed."
        assert self.can_redo

        entry_to_redo = self.next_sequence_number - 2 * self.undo_count

        with self.cache_lock:
            action, log_number, _, _ = self._get_history_entry(
                entry_to_redo)

            self.redo_count += 1
            history_entry = (
                action, log_number,
                self.undo_count, self.redo_count)

            self._add_history_entry(history_entry)

            self._schedule_log_write(
                self.next_sequence_number, history_entry, None)

            self.next_sequence_number += 1

    @property
    def logs_since_last_checkpoint(self):
        if self.next_checkpoint_number == 0:
            return self.next_sequence_number
        seq_number, _ = self._get_checkpoint_entry(
            self.next_checkpoint_number - 1)
        return self.next_sequence_number - seq_number

    def add_checkpoint(self, checkpoint):
        self._schedule_checkpoint_write(
            self.next_sequence_number, self.next_checkpoint_number,
            checkpoint)

        packed_index_entry = self.checkpoint_index_formatter.pack(
            self.next_sequence_number, self.next_checkpoint_number)
        self.checkpoint_index += packed_index_entry
        self.next_checkpoint_number += 1

    def get_checkpoint(self, checkpoint_number):
        _, checkpoint_number = self._get_checkpoint_entry(
            checkpoint_number)

        checkpoint_path = os.path.join(
            self.data_dir,
            'checkpoint.%06d' % checkpoint_number)
        logger.info("Reading checkpoint %s...", checkpoint_path)
        with open(checkpoint_path, mode='rb') as fp:
            return fp.read()