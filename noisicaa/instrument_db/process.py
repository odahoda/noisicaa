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
import time
from typing import cast, List, Set  # pylint: disable=unused-import

from noisicaa import constants
from noisicaa import core

from .private import db
from . import process_base
from . import mutations as mutations_lib  # pylint: disable=unused-import

logger = logging.getLogger(__name__)


class Session(core.CallbackSessionMixin, core.SessionBase):
    def __init__(self, client_address: str, flags: Set[str], **kwargs) -> None:
        super().__init__(callback_address=client_address, **kwargs)
        self.__flags = flags or set()
        self.__pending_mutations = []  # type: List[mutations_lib.Mutation]

    def callback_connected(self) -> None:
        logger.info(
            "Client callback connection established, sending %d pending mutations.",
            len(self.__pending_mutations))
        self.publish_mutations(self.__pending_mutations)
        self.__pending_mutations.clear()

    def publish_mutations(self, mutations: List[mutations_lib.Mutation]) -> None:
        if not mutations:
            return

        if not self.callback_alive:
            self.__pending_mutations.extend(mutations)
            return

        self.async_callback('INSTRUMENTDB_MUTATIONS', list(mutations))


class InstrumentDBProcess(process_base.InstrumentDBProcessBase):
    session_cls = Session

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.db = None  # type: db.InstrumentDB
        self.search_paths = [
            '/usr/share/sounds/sf2/',
            '/data/instruments/',
        ]

    async def setup(self) -> None:
        await super().setup()

        self.db = db.InstrumentDB(self.event_loop, constants.CACHE_DIR)
        self.db.setup()
        self.db.add_mutations_listener(self.publish_mutations)
        if time.time() - self.db.last_scan_time > 3600:
            self.db.start_scan(self.search_paths, True)

    async def cleanup(self) -> None:
        if self.db is not None:
            self.db.cleanup()
            self.db = None

        await super().cleanup()

    def publish_mutations(self, mutations: List[mutations_lib.Mutation]) -> None:
        for session in self.sessions:
            session = cast(Session, session)
            session.publish_mutations(mutations)

    async def session_started(self, session: core.SessionBase) -> None:
        session = cast(Session, session)
        # Send initial mutations to build up the current pipeline
        # state.
        session.publish_mutations(list(self.db.initial_mutations()))

    async def handle_start_scan(self, session_id: str) -> None:
        self.get_session(session_id)
        self.db.start_scan(self.search_paths, True)


class InstrumentDBSubprocess(core.SubprocessMixin, InstrumentDBProcess):
    pass
