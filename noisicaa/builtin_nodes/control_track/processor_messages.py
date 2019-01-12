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

from noisicaa import audioproc
from noisicaa.builtin_nodes import processor_message_registry_pb2

def add_control_point(
        node_id: str,
        id: int,  # pylint: disable=redefined-builtin
        time: audioproc.MusicalTime,
        value: float
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.cvgenerator_add_control_point]
    pb.id = id
    pb.time.CopyFrom(time.to_proto())
    pb.value = value
    return msg

def remove_control_point(
        node_id: str,
        id: int  # pylint: disable=redefined-builtin
) -> audioproc.ProcessorMessage:
    msg = audioproc.ProcessorMessage(node_id=node_id)
    pb = msg.Extensions[processor_message_registry_pb2.cvgenerator_remove_control_point]
    pb.id = id
    return msg
