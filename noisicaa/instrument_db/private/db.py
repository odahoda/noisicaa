#!/usr/bin/python3

import glob
import os
import os.path
import logging
import pickle
import queue
import threading
import time

from noisicaa import core
from noisicaa import instrument_db

from . import sample_scanner
from . import soundfont_scanner

logger = logging.getLogger(__name__)


class ScanAborted(Exception):
    pass


class InstrumentDB(object):
    VERSION = 2

    def __init__(self, event_loop, cache_dir):
        self.event_loop = event_loop
        self.cache_dir = cache_dir

        self.listeners = core.CallbackRegistry()

        self.instruments = None
        self.file_map = None
        self.last_scan_time = None
        self.scan_thread = None
        self.scan_commands = queue.Queue()
        self.stopping = threading.Event()

    def setup(self):
        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir)

        cache_data = self.load_cache(self.cache_path, None)
        if cache_data is not None:
            logger.info("Loaded cached instrument database.")
            self.instruments = cache_data['instruments']
            self.file_map = cache_data['file_map']
            self.last_scan_time = cache_data['last_scan_time']
            logger.info("%d instruments.", len(self.instruments))
            logger.info("last scan: %s.", time.ctime(self.last_scan_time))
        else:
            logger.info("Starting with empty instrument database.")
            self.instruments = {}
            self.file_map = {}
            self.last_scan_time = 0

        self.scan_thread = threading.Thread(target=self.scan_main)
        self.scan_thread.start()

    def cleanup(self):
        if self.scan_thread is not None:
            self.scan_commands.put(('STOP',))
            self.stopping.set()
            self.scan_thread.join()
            self.scan_thread = None

    def add_mutations_listener(self, callback):
        return self.listeners.add('db_mutations', callback)

    def load_cache(self, path, default):
        if not os.path.isfile(path):
            return default

        with open(path, 'rb') as fp:
            cached = pickle.load(fp)

        if not isinstance(cached, dict):
            return default

        if cached.get('version', -1) != self.VERSION:
            return default

        return cached.get('data', default)

    def store_cache(self, path, data):
        cached = {
            'version': self.VERSION,
            'data': data,
        }

        with open(path + '.new', 'wb') as fp:
            pickle.dump(cached, fp)

        os.replace(path + '.new', path)

    @property
    def cache_path(self):
        return os.path.join(self.cache_dir, 'instrument_db.cache')

    def publish_scan_state(self, state, *args):
        self.event_loop.call_soon_threadsafe(
            self.listeners.call, 'scan-state', state, *args)

    def add_instruments(self, descriptions):
        for description in descriptions:
            self.instruments[description.uri] = description

        self.listeners.call(
            'db_mutations',
            [instrument_db.AddInstrumentDescription(description)
             for description in descriptions])

    def scan_main(self):
        while not self.stopping.is_set():
            cmd, *args = self.scan_commands.get()
            if cmd == 'STOP':
                break
            elif cmd == 'SCAN':
                self.do_scan(*args)
            else:
                raise ValueError(cmd)

    def update_cache(self):
        cache_data = {
            'instruments': self.instruments,
            'file_map': self.file_map,
            'last_scan_time': self.last_scan_time,
            }
        self.store_cache(self.cache_path, cache_data)

    def do_scan(self, search_paths, incremental):
        try:
            file_list = self.collect_files(search_paths, incremental)
            self.scan_files(file_list)
            self.last_scan_time = time.time()
            self.update_cache()
        except ScanAborted:
            logger.warning("Scan was aborted.")
            self.publish_scan_state('aborted')

    def collect_files(self, search_paths, incremental):
        logger.info("Collecting files (incremental=%s)", incremental)
        self.publish_scan_state('prepare')

        seen_files = set()
        file_list = []
        for root_path in search_paths:
            logger.info("Collecting files from %s", root_path)

            for dname, dirs, files in os.walk(root_path):
                if self.stopping.is_set():
                    raise ScanAborted

                for fname in sorted(files):
                    path = os.path.join(dname, fname)
                    path = os.path.abspath(path)
                    if path in seen_files:
                        continue

                    if incremental and os.path.getmtime(path) == self.file_map.get(path, -1):
                        continue

                    seen_files.add(path)
                    file_list.append(path)

        if incremental:
            logger.info("%d new/modified files found.", len(file_list))
        else:
            logger.info("%d files found.", len(file_list))

        return file_list

    def scan_files(self, file_list):
        scanners = [
            sample_scanner.SampleScanner(),
            soundfont_scanner.SoundFontScanner(),
        ]

        batch = []
        for idx, path in enumerate(file_list):
            if self.stopping.is_set():
                raise ScanAborted

            logger.info("Scanning file %s...", path)
            self.publish_scan_state('scan', idx, len(file_list))

            for scanner in scanners:
                for description in scanner.scan(path):
                    batch.append(description)
                    if len(batch) > 10:
                        self.event_loop.call_soon_threadsafe(
                            self.add_instruments, list(batch))
                        batch.clear()

            self.file_map[path] = os.path.getmtime(path)

        if batch:
            self.event_loop.call_soon_threadsafe(
                self.add_instruments, list(batch))
            batch.clear()

        self.publish_scan_state('complete')

    def initial_mutations(self):
        for uri, description in sorted(self.instruments.items()):
            yield instrument_db.AddInstrumentDescription(description)

    def start_scan(self, search_paths, incremental):
        self.scan_commands.put(('SCAN', list(search_paths), incremental))
