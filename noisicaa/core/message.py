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

# mypy: loose

import logging

# pylint/mypy doesn't know about the capnp import magic.
import capnp  # pylint: disable=unused-import
# pylint: disable=no-name-in-module
from . import message_capnp  # type: ignore

logger = logging.getLogger(__name__)


MessageKey = message_capnp.Key
MessageType = message_capnp.Type

def build_labelset(labels):
    lset = message_capnp.Labelset.new_message()
    lset.init('labels', len(labels))
    for i, (k, v) in enumerate(sorted(labels.items())):
        label = lset.labels[i]
        label.key = k
        label.value = v
    return lset

def build_message(labels, type, data):  # pylint: disable=redefined-builtin
    msg = message_capnp.Message.new_message()
    msg.init('labelset')
    msg.labelset.init('labels', len(labels))
    for i, (k, v) in enumerate(sorted(labels.items())):
        label = msg.labelset.labels[i]
        label.key = k
        label.value = v
    msg.type = type
    msg.data = data
    return msg
