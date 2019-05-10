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
from noisicaa import node_db
from noisicaa import audioproc
from noisicaa.music import node_connector
from . import processor_messages
from . import node_description
from . import _model

logger = logging.getLogger(__name__)


class Connector(node_connector.NodeConnector):
    _node = None  # type: MidiSource

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]

    def _init_internal(self) -> None:
        self._emit_message(processor_messages.update(
            self.__node_id,
            device_uri=self._node.device_uri,
            channel_filter=self._node.channel_filter))

        self.__listeners['device_uri'] = self._node.device_uri_changed.add(
            lambda change: self._emit_message(processor_messages.update(
                self.__node_id,
                device_uri=change.new_value)))
        self.__listeners['channel_filter'] = self._node.channel_filter_changed.add(
            lambda change: self._emit_message(processor_messages.update(
                self.__node_id,
                channel_filter=change.new_value)))

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()


class MidiSource(_model.MidiSource):
    def create(
            self, *,
            device_uri: Optional[str] = '',
            channel_filter: Optional[int] = -1,
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.device_uri = device_uri

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> Connector:
        return Connector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.MidiSourceDescription
