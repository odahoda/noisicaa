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

import io
import logging
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


class PresetError(Exception):
    pass

class PresetLoadError(PresetError):
    pass


class Preset(object):
    def __init__(self, *, display_name, node_uri, node_description):
        self.display_name = display_name
        self.node_uri = node_uri
        self.node_description = node_description

    @classmethod
    def from_file(cls, path, node_factory):
        logger.info("Loading preset from %s", path)
        with open(path, 'rb') as fp:
            return cls.parse(fp, node_factory)

    @classmethod
    def from_string(cls, xml, node_factory):
        stream = io.BytesIO(xml.encode('utf-8'))
        return cls.parse(stream, node_factory)

    @classmethod
    def parse(cls, stream, node_factory):
        tree = ElementTree.parse(stream)
        root = tree.getroot()
        if root.tag != 'preset':
            raise PresetLoadError("Expected <preset> root element, found <%s>" % root.tag)

        node_elem = root.find('node')
        if node_elem is None:
            raise PresetLoadError("Missing <node> element.")

        node_uri = node_elem.get('uri', None)
        if node_uri is None:
            raise PresetLoadError("Missing uri attribute on <node> element.")

        node_desc = node_factory(node_uri)
        if node_desc is None:
            raise PresetLoadError("Node %s does not exist." % node_uri)

        display_name = ''.join(root.find('display-name').itertext())

        return cls(
            display_name=display_name,
            node_uri=node_uri,
            node_description=node_desc)

    def to_bytes(self):
        doc = ElementTree.Element('preset', version='1')
        doc.text = '\n'
        doc.tail = '\n'

        node_uri_elem = ElementTree.SubElement(doc, 'node_uri')
        node_uri_elem.text = self.node_uri
        node_uri_elem.tail = '\n'

        tree = ElementTree.ElementTree(doc)
        buf = io.BytesIO()
        tree.write(buf, encoding='utf-8', xml_declaration=True)
        return buf.getvalue()
