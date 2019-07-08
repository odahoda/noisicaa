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

import itertools
import json
import re
from typing import Any, Dict, Iterable, Iterator

import pyparsing

from . import node_description_pb2

COLON = pyparsing.Suppress(':')
SEMICOLON = pyparsing.Suppress(';')
LBRACE = pyparsing.Suppress('{')
RBRACE = pyparsing.Suppress('}')

MENU_ITEM_LABEL = pyparsing.QuotedString(quoteChar='\'', unquoteResults=True)
MENU_ITEM_VALUE = pyparsing.Word('0123456789.')
MENU_ITEM = pyparsing.Group(MENU_ITEM_LABEL + COLON + MENU_ITEM_VALUE)
MENU_SPEC = LBRACE + MENU_ITEM + pyparsing.OneOrMore(SEMICOLON + MENU_ITEM) + RBRACE

def _set_port_attr(port_desc: node_description_pb2.PortDescription, key: str, value: str) -> None:
    if key == 'name':
        port_desc.name = value
    elif key == 'display_name':
        port_desc.display_name = value
    elif key == 'type':
        port_desc.types[:] = [node_description_pb2.PortDescription.Type.Value(value)]
    elif key == 'scale':
        if value == 'log':
            port_desc.float_value.scale = node_description_pb2.FloatValueDescription.LOG
        else:
            raise ValueError("Unknown scale type '%s'" % value)
    elif key == 'float_value':
        p = value.split()
        port_desc.float_value.min = float(p[0])
        port_desc.float_value.max = float(p[1])
        port_desc.float_value.default = float(p[2])
    elif key == 'style':
        m = re.match(r'[a-zA-Z_]+\b', value)
        if not m:
            raise ValueError("Malformed style spec '%s'" % value)
        style = m.group(0)
        if style == 'menu':
            value = value[len(style):].strip()
            try:
                menu_spec = MENU_SPEC.parseString(value)
            except pyparsing.ParseException as exc:
                raise ValueError("Malformed menu spec '%s': %s" % (value, exc))

            for name, value in menu_spec:
                port_desc.enum_value.items.add(name=name, value=float(value))
        else:
            raise ValueError("Unknown style '%s'" % style)
    else:
        raise ValueError("Unknown meta key '%s'" % key)


def _list_controls(items: Iterable[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    for item in items:
        if item['type'] in {'vgroup', 'hgroup', 'tgroup'}:
            yield from _list_controls(item['items'])
        elif item['type'] in {'nentry', 'hslider', 'vslider'}:
            yield item
        else:
            raise ValueError("Unsupported UI item type '%s'" % item['type'])


REQUIRED_PORT_FIELDS = ['name', 'direction']

def faust_json_to_node_description(path: str) -> node_description_pb2.NodeDescription:
    node_desc = node_description_pb2.NodeDescription(
        type=node_description_pb2.NodeDescription.PROCESSOR,
        node_ui=node_description_pb2.NodeUIDescription(
            type='builtin://generic',
        ),
        builtin_icon='node-type-builtin',
    )

    with open(path, 'r', encoding='utf-8') as fp:
        faust_desc = json.load(fp)

        meta = dict(itertools.chain.from_iterable(m.items() for m in faust_desc['meta']))

        node_desc.display_name = faust_desc['name']
        node_desc.uri = meta['uri']
        node_desc.processor.type = meta['uri']

        for port_num in range(int(faust_desc['inputs'])):
            port_desc = node_desc.ports.add()
            port_desc.direction = node_description_pb2.PortDescription.INPUT

            for key, value in meta.items():
                if not key.startswith('input%d_' % port_num):
                    continue
                key = key.split('_', 1)[1]
                _set_port_attr(port_desc, key, value)

            for field in REQUIRED_PORT_FIELDS:
                if not port_desc.HasField(field):
                    raise ValueError("Missing field '%s' for input port %d" % (field, port_num))

        for port_num in range(int(faust_desc['outputs'])):
            port_desc = node_desc.ports.add()
            port_desc.direction = node_description_pb2.PortDescription.OUTPUT

            for key, value in meta.items():
                if not key.startswith('output%d_' % port_num):
                    continue
                key = key.split('_', 1)[1]
                _set_port_attr(port_desc, key, value)

            for field in REQUIRED_PORT_FIELDS:
                if not port_desc.HasField(field):
                    raise ValueError("Missing field '%s' for output port %d" % (field, port_num))

        for control in _list_controls(faust_desc['ui']):
            control_meta = dict(itertools.chain.from_iterable(m.items() for m in control['meta']))

            if control['type'] in {'nentry', 'hslider', 'vslider'}:
                port_desc = node_desc.ports.add()
                port_desc.name = control['label']
                port_desc.direction = node_description_pb2.PortDescription.INPUT
                port_desc.types[:] = [node_description_pb2.PortDescription.KRATE_CONTROL]
                for key, value in control_meta.items():
                    _set_port_attr(port_desc, key, value)

                if port_desc.HasField('enum_value'):
                    port_desc.enum_value.default = float(control['init'])
                else:
                    port_desc.float_value.min = float(control['min'])
                    port_desc.float_value.max = float(control['max'])
                    port_desc.float_value.default = float(control['init'])
            else:
                raise AssertionError(control['type'])

    return node_desc
