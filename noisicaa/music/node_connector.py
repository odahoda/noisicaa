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
from typing import Callable, List

from noisicaa import audioproc
from . import pmodel

logger = logging.getLogger(__name__)


class NodeConnector(pmodel.NodeConnector):
    def __init__(
            self, *,
            node: pmodel.BasePipelineGraphNode,
            message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> None:
        super().__init__()

        self._node = node
        self.__message_cb = message_cb

        self.__initializing = True
        self.__initial_messages = []  # type: List[audioproc.ProcessorMessage]

    def init(self) -> List[audioproc.ProcessorMessage]:
        assert self.__initializing
        self._init_internal()
        self.__initializing = False
        messages = self.__initial_messages
        self.__initial_messages = None
        return messages

    def _init_internal(self) -> None:
        raise NotImplementedError

    def _emit_message(self, msg: audioproc.ProcessorMessage) -> None:
        if self.__initializing:
            self.__initial_messages.append(msg)
        else:
            self.__message_cb(msg)

    def close(self) -> None:
        pass
