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

from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2
from . import model


def update(
        node: model.CustomCSound, *,
        set_orchestra: str = None,
        set_score: str = None
) -> music.Command:
    cmd = music.Command(command='update_custom_csound')
    pb = cmd.Extensions[commands_registry_pb2.update_custom_csound]
    pb.node_id = node.id
    if set_orchestra is not None:
        pb.set_orchestra = set_orchestra
    if set_score is not None:
        pb.set_score = set_score
    return cmd


def create_port(
        node: model.CustomCSound,
        name: str,
        index: int = None,
) -> music.Command:
    cmd = music.Command(command='create_custom_csound_port')
    pb = cmd.Extensions[commands_registry_pb2.create_custom_csound_port]
    pb.node_id = node.id
    pb.name = name
    if index is not None:
        pb.index = index
    return cmd

def delete_port(
        port: model.CustomCSoundPort,
) -> music.Command:
    cmd = music.Command(command='delete_custom_csound_port')
    pb = cmd.Extensions[commands_registry_pb2.delete_custom_csound_port]
    pb.port_id = port.id
    return cmd
