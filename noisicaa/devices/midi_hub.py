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

import logging
import select
import threading
from typing import Any, Iterator, Dict, Tuple  # pylint: disable=unused-import

from noisicaa.core import callbacks
from . import libalsa
from . import midi_events

logger = logging.getLogger(__name__)


class Error(Exception):
    pass


class MidiHub(object):
    def __init__(self, sequencer: libalsa.AlsaSequencer) -> None:
        self.sequencer = sequencer
        self.__thread = None  # type: threading.Thread
        self.__quit_event = None  # type: threading.Event
        self.__started = False
        self.listeners = callbacks.CallbackRegistry(self.__listener_changed)

        self.__connected = None  # type: Dict[str, int]

    def __listener_changed(self, target: str, listener_id: str, add_or_remove: bool) -> None:
        assert self.__started, "MidiHub must be started before adding listeners."

        if add_or_remove:
            refcount = self.__connected.setdefault(target, 0)
            if refcount == 0:
                for port_info in self.sequencer.list_all_ports():
                    if port_info.device_id == target:
                        logger.info("Connecting to %s", port_info)
                        self.sequencer.connect(port_info)
                        break
                else:
                    raise Error("Device %s not found" % target)

            self.__connected[target] += 1

        else:
            assert target in self.__connected
            self.__connected[target] -= 1

            if self.__connected[target] == 0:
                del self.__connected[target]

                for port_info in self.sequencer.list_all_ports():
                    if port_info.device_id == target:
                        logger.info("Disconnecting from %s", port_info)
                        self.sequencer.disconnect(port_info)
                        break
                else:
                    raise Error("Device %s not found" % target)

    def __enter__(self) -> 'MidiHub':
        self.start()
        return self

    def __exit__(self, *args: Any) -> bool:
        self.stop()
        return False

    def start(self) -> None:
        logger.info("Starting MidiHub...")

        self.__connected = {}

        #port_info = next(
        #    p for p in self.sequencer.list_all_ports()
        #    if 'read' in p.capabilities and 'hardware' in p.types)
        #self.sequencer.connect(port_info)

        self.__quit_event = threading.Event()
        self.__thread = threading.Thread(target=self.__thread_main, name="MidiHub")
        self.__thread.start()
        logger.info("MidiHub started.")

        self.__started = True

    def stop(self) -> None:
        self.__started = False

        logger.info("Stopping MidiHub...")
        if self.__thread is not None:
            self.__quit_event.set()
            self.__thread.join()
            self.__thread = None
            self.__quit_event = None

        logger.info("MidiHub stopped.")

    def list_devices(self) -> Iterator[Tuple[str, libalsa.PortInfo]]:
        for port_info in self.sequencer.list_all_ports():
            if 'read' not in port_info.capabilities:
                continue
            if 'midi_generic' not in port_info.types:
                continue
            yield (port_info.device_id, port_info)

    def __thread_main(self) -> None:
        poller = select.poll()

        # TODO: Can the list of FDs change over time? E.g. when ports are
        # created/removed?
        for fd in self.sequencer.get_pollin_fds():
            poller.register(fd, select.POLLIN)

        while not self.__quit_event.is_set():
            # TODO: Poll w/o timeout and have quit_tread() ping some FD,
            # so this gets unstuck.
            poller.poll(10)
            event = self.sequencer.get_event()
            if event is not None:
                self.dispatch_midi_event(event)

    def dispatch_midi_event(self, event: midi_events.MidiEvent) -> None:
        logger.info("Dispatching MIDI event %s", event)
        self.listeners.call(event.device_id, event)
