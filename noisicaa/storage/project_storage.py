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

from noisicaa.core import fileutil

logger = logging.getLogger(__name__)


class ProjectStorage(object):
    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    ACTION_LOG_ENTRY = b'e'
    ACTION_UNDO = b'u'
    ACTION_REDO = b'r'

    LOG_ENTRY_CACHE_SIZE = 20

    def __init__(self):
        self.path = None
        self.data_dir = None
        self.header_data = None
        self.file_lock = None
        self.log_index_fp = None
        self.log_history_fp = None
        self.checkpoint_index_fp = None

        self.next_log_number = 0
        self.log_file_number = 0
        self.log_fp_map = {}
        self.log_index_formatter = struct.Struct('>QQ')
        self.log_index = bytearray()

        self.log_history_formatter = struct.Struct('>cQQQ')
        self.next_sequence_number = 0
        self.undo_count = 0
        self.redo_count = 0
        self.log_history = bytearray()

        self.next_checkpoint_number = 0
        self.checkpoint_index_formatter = struct.Struct('>QQ')
        self.checkpoint_index = bytearray()

        self.cache_lock = threading.RLock()
        self.log_entry_cache = collections.OrderedDict()

        self.write_queue = queue.Queue()
        self.writer_thread = threading.Thread(target=self._writer_main)
        self.written_log_number = -1
        self.written_sequence_number = -1

    @classmethod
    def open(cls, path):
        raise NotImplementedError

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

        file_lock = cls.acquire_file_lock(
            os.path.join(data_dir, 'lock'))

        log_index_fp = open(
            os.path.join(data_dir, 'log.index'),
            mode='wb', buffering=0)

        log_history_fp = open(
            os.path.join(data_dir, 'log.history'),
            mode='wb', buffering=0)

        checkpoint_index_fp = open(
            os.path.join(data_dir, 'checkpoint.index'),
            mode='wb', buffering=0)

        fp = fileutil.File(path)
        fp.write_json(
            header_data,
            fileutil.FileInfo(
                filetype='project-header',
                version=cls.VERSION))

        project_storage = cls()
        project_storage.path = path
        project_storage.file_lock = file_lock
        project_storage.data_dir = data_dir
        project_storage.header_data = header_data
        project_storage.log_index_fp = log_index_fp
        project_storage.log_history_fp = log_history_fp
        project_storage.checkpoint_index_fp = checkpoint_index_fp
        project_storage.writer_thread.start()
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

    def _schedule_checkpoint_write(self, seq_number, checkpoint):
        assert self.writer_thread.is_alive()
        self.write_queue.put(
            ('CHECKPOINT', (seq_number, checkpoint)))

    def _writer_main(self):
        logger.info("Log writer thread started.")

        log_fp = open(
            os.path.join(
                self.data_dir,
                'log.%06d' % self.log_file_number),
            mode='w+b', buffering=0)
        while True:
            cmd, arg = self.write_queue.get()
            if cmd == 'STOP':
                break
            elif cmd == 'FLUSH':
                arg.set()
            elif cmd == 'LOG':
                seq_number, history_entry, log_entry = arg
                action, log_number, _, _ = history_entry

                logger.info("Writing log entry #%d...", seq_number)

                assert (
                    action != self.ACTION_LOG_ENTRY or log_entry is not None)
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
                seq_number, checkpoint = arg

                checkpoint_path = os.path.join(
                    self.data_dir,
                    'checkpoint.%06d' % self.next_checkpoint_number)
                logger.info("Writing checkpoint %s...", checkpoint_path)
                with open(checkpoint_path, mode='wb', buffering=0) as fp:
                    fp.write(checkpoint)

                packed_index_entry = self.checkpoint_index_formatter.pack(
                    seq_number, self.next_checkpoint_number)
                self.checkpoint_index_fp.write(packed_index_entry)
                self.checkpoint_index_fp.flush()

                with self.cache_lock:
                    self.checkpoint_index += packed_index_entry
                    self.next_checkpoint_number += 1
            else:
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

        entry_len = struct.unpack(
            '>Q', log_fp.read(struct.calcsize('>Q')))
        return log_fp.read(entry_len)

    def _get_log_entry(self, log_number):
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

            entries_to_drop = (
                len(self.log_entry_cache) - self.LOG_ENTRY_CACHE_SIZE)
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

    def append_log_entry(self, entry):
        assert self.path is not None, "Project already closed."

        with self.cache_lock:
            assert self.next_log_number not in self.log_entry_cache

            self.undo_count = 0
            self.redo_count = 0

            history_entry = (
                self.ACTION_LOG_ENTRY, self.next_log_number,
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
        assert action == self.ACTION_LOG_ENTRY
        return self._get_log_entry(log_number)

    def get_log_entry_to_redo(self):
        assert self.can_redo

        entry_to_redo = self.next_sequence_number - 2 * self.undo_count

        action, log_number, _, _ = (
            self._get_history_entry(entry_to_redo))
        assert action == self.ACTION_LOG_ENTRY
        return self._get_log_entry(log_number)

    def undo(self):
        assert self.path is not None, "Project already closed."
        assert self.can_undo

        entry_to_undo = (
            self.next_sequence_number - 2 * self.undo_count - 1)

        with self.cache_lock:
            _, log_number, _, _ = self._get_history_entry(entry_to_undo)

            self.undo_count += 1
            history_entry = (
                self.ACTION_UNDO, log_number,
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
            _, log_number, _, _ = self._get_history_entry(entry_to_redo)

            self.redo_count += 1
            history_entry = (
                self.ACTION_REDO, log_number,
                self.undo_count, self.redo_count)

            self._add_history_entry(history_entry)

            self._schedule_log_write(
                self.next_sequence_number, history_entry, None)

            self.next_sequence_number += 1

    def add_checkpoint(self, checkpoint):
        self._schedule_checkpoint_write(
            self.next_sequence_number, checkpoint)
