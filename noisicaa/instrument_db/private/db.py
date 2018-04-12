#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

import asyncio
import os
import os.path
import logging
import pickle
import queue
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Set, Iterable  # pylint: disable=unused-import

from noisicaa import core
from noisicaa import instrument_db

from . import sample_scanner
from . import soundfont_scanner

logger = logging.getLogger(__name__)


class ScanAborted(Exception):
    pass


class InstrumentDB(object):
    VERSION = 2

    def __init__(self, event_loop: asyncio.AbstractEventLoop, cache_dir: str) -> None:
        self.listeners = core.CallbackRegistry()

        self.__event_loop = event_loop
        self.__cache_dir = cache_dir

        self.__instruments = None  # type: Dict[str, instrument_db.InstrumentDescription]
        self.__file_map = None  # type: Dict[str, float]
        self.__last_scan_time = None  # type: float
        self.__scan_thread = None  # type: threading.Thread
        self.__scan_commands = queue.Queue()  # type: queue.Queue
        self.__stopping = threading.Event()  # type: threading.Event

    @property
    def last_scan_time(self) -> float:
        return self.__last_scan_time

    def setup(self) -> None:
        if not os.path.isdir(self.__cache_dir):
            os.makedirs(self.__cache_dir)

        cache_data = self.__load_cache(self.__cache_path, None)
        if cache_data is not None:
            logger.info("Loaded cached instrument database.")
            self.__instruments = cache_data['instruments']
            self.__file_map = cache_data['file_map']
            self.__last_scan_time = cache_data['last_scan_time']
            logger.info("%d instruments.", len(self.__instruments))
            logger.info("last scan: %s.", time.ctime(self.__last_scan_time))
        else:
            logger.info("Starting with empty instrument database.")
            self.__instruments = {}
            self.__file_map = {}
            self.__last_scan_time = 0

        self.__scan_thread = threading.Thread(target=self.__scan_main)
        self.__scan_thread.start()

    def cleanup(self) -> None:
        if self.__scan_thread is not None:
            self.__scan_commands.put(('STOP',))
            self.__stopping.set()
            self.__scan_thread.join()
            self.__scan_thread = None

    def add_mutations_listener(
            self, callback: Callable[[List[instrument_db.Mutation]], None]) -> core.Listener:
        return self.listeners.add('db_mutations', callback)

    def __load_cache(self, path: str, default: Dict[str, Any]) -> Dict[str, Any]:
        if not os.path.isfile(path):
            return default

        with open(path, 'rb') as fp:
            cached = pickle.load(fp)

        if not isinstance(cached, dict):
            return default

        if cached.get('version', -1) != self.VERSION:
            return default

        return cached.get('data', default)

    def __store_cache(self, path: str, data: Dict[str, Any]) -> None:
        cached = {
            'version': self.VERSION,
            'data': data,
        }

        with open(path + '.new', 'wb') as fp:
            pickle.dump(cached, fp)

        os.replace(path + '.new', path)

    @property
    def __cache_path(self) -> str:
        return os.path.join(self.__cache_dir, 'instrument_db.cache')

    def __publish_scan_state(self, state: str, *args: Any) -> None:
        self.__event_loop.call_soon_threadsafe(
            self.listeners.call, 'scan-state', state, *args)

    def __add_instruments(self, descriptions: List[instrument_db.InstrumentDescription]) -> None:
        for description in descriptions:
            self.__instruments[description.uri] = description

        self.listeners.call(
            'db_mutations',
            [instrument_db.AddInstrumentDescription(description)
             for description in descriptions])

    def __scan_main(self) -> None:
        try:
            while not self.__stopping.is_set():
                cmd, *args = self.__scan_commands.get()
                if cmd == 'STOP':
                    break
                elif cmd == 'SCAN':
                    self.__do_scan(*args)
                else:
                    raise ValueError(cmd)

        except:  # pylint: disable=bare-except
            sys.stdout.flush()
            sys.excepthook(*sys.exc_info())
            sys.stderr.flush()
            os._exit(1)  # pylint: disable=protected-access

    def __update_cache(self) -> None:
        cache_data = {
            'instruments': self.__instruments,
            'file_map': self.__file_map,
            'last_scan_time': self.__last_scan_time,
            }
        self.__store_cache(self.__cache_path, cache_data)

    def __do_scan(self, search_paths: List[str], incremental: bool) -> None:
        try:
            file_list = self.__collect_files(search_paths, incremental)
            self.__scan_files(file_list)
            self.__last_scan_time = time.time()
            self.__update_cache()
        except ScanAborted:
            logger.warning("Scan was aborted.")
            self.__publish_scan_state('aborted')

    def __collect_files(self, search_paths: List[str], incremental: bool) -> List[str]:
        logger.info("Collecting files (incremental=%s)", incremental)
        self.__publish_scan_state('prepare')

        seen_files = set()  # type: Set[str]
        file_list = []
        for root_path in search_paths:
            logger.info("Collecting files from %s", root_path)

            for dname, _, files in os.walk(root_path):
                if self.__stopping.is_set():
                    raise ScanAborted

                for fname in sorted(files):
                    path = os.path.join(dname, fname)
                    path = os.path.abspath(path)
                    if path in seen_files:
                        continue

                    if incremental and os.path.getmtime(path) == self.__file_map.get(path, -1):
                        continue

                    seen_files.add(path)
                    file_list.append(path)

        if incremental:
            logger.info("%d new/modified files found.", len(file_list))
        else:
            logger.info("%d files found.", len(file_list))

        return file_list

    def __scan_files(self, file_list: List[str]) -> None:
        scanners = [
            sample_scanner.SampleScanner(),
            soundfont_scanner.SoundFontScanner(),
        ]

        batch = []
        for idx, path in enumerate(file_list):
            if self.__stopping.is_set():
                raise ScanAborted

            logger.info("Scanning file %s...", path)
            self.__publish_scan_state('scan', idx, len(file_list))

            for scanner in scanners:
                for description in scanner.scan(path):
                    batch.append(description)
                    if len(batch) > 10:
                        self.__event_loop.call_soon_threadsafe(
                            self.__add_instruments, list(batch))
                        batch.clear()

            self.__file_map[path] = os.path.getmtime(path)

        if batch:
            self.__event_loop.call_soon_threadsafe(
                self.__add_instruments, list(batch))
            batch.clear()

        self.__publish_scan_state('complete')

    def initial_mutations(self) -> Iterable[instrument_db.Mutation]:
        for _, description in sorted(self.__instruments.items()):
            yield instrument_db.AddInstrumentDescription(description)

    def start_scan(self, search_paths: List[str], incremental: bool) -> None:
        self.__scan_commands.put(('SCAN', list(search_paths), incremental))
