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

import logging
from typing import Any, Optional, Dict, Callable

from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import instrument_db
from noisicaa.music import node_connector
from . import node_description
from . import processor_messages
from . import _model

logger = logging.getLogger(__name__)


class Connector(node_connector.NodeConnector):
    _node = None  # type: Instrument

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]

    def _init_internal(self) -> None:
        self.__change_instrument(self._node.instrument_uri)

        self.__listeners['instrument_uri'] = self._node.instrument_uri_changed.add(
            lambda change: self.__change_instrument(change.new_value))

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __change_instrument(self, instrument_uri: str) -> None:
        try:
            instrument_spec = instrument_db.create_instrument_spec(instrument_uri)
        except instrument_db.InvalidInstrumentURI as exc:
            logger.error("Invalid instrument URI '%s': %s", instrument_uri, exc)
            return

        self._emit_message(processor_messages.change_instrument(
            self.__node_id, instrument_spec))


class Instrument(_model.Instrument):
    def create(self, *, instrument_uri: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.instrument_uri = instrument_uri

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> Connector:
        return Connector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.InstrumentDescription
