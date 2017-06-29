#!/usr/bin/python3

import logging

import capnp

from . import message_capnp

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

def build_message(labels, type, data):
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
