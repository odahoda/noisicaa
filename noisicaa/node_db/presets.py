#!/usr/bin/python3

import io
import logging
from xml.etree import ElementTree

from . import node_description

logger = logging.getLogger(__name__)


class PresetError(Exception):
    pass

class PresetLoadError(PresetError):
    pass


class Preset(object):
    def __init__(self, *, display_name, node_uri, node_description, parameter_values):
        self.display_name = display_name
        self.node_uri = node_uri
        self.node_description = node_description
        self.parameter_values = {}
        if parameter_values is not None:
            self.parameter_values.update(parameter_values)

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
        if node_description is None:
            raise PresetLoadError("Node %s does not exist." % node_uri)

        parameter_values = {}
        for parameter_elem in root.find('parameter-values').findall('parameter'):
            parameter_name = parameter_elem.get('name', None)
            if parameter_name is None:
                raise PresetLoadError("Missing name attribute on <parameter> element.")

            try:
                parameter_desc = node_desc.get_parameter(parameter_name)
            except KeyError:
                logger.warning("Skipping unknown parameter '%s'", parameter_name)
                continue

            if parameter_desc.param_type in (
                    node_description.ParameterType.String,
                    node_description.ParameterType.Path):
                value = parameter_elem.get('value')
            elif parameter_desc.param_type == node_description.ParameterType.Float:
                value = float(parameter_elem.get('value'))
            elif parameter_desc.param_type == node_description.ParameterType.Text:
                value = ''.join(parameter_elem.itertext())
                if value.startswith('\n'):
                    value = value[1:]
            else:
                raise ValueError(parameter_desc.param_type)

            parameter_values[parameter_name] = value

        display_name = ''.join(root.find('display-name').itertext())

        return cls(
            display_name=display_name,
            node_uri=node_uri,
            node_description=node_desc,
            parameter_values=parameter_values)

    def to_bytes(self):
        doc = ElementTree.Element('preset', version='1')
        doc.text = '\n'
        doc.tail = '\n'

        node_uri_elem = ElementTree.SubElement(doc, 'node_uri')
        node_uri_elem.text = self.node_uri
        node_uri_elem.tail = '\n'

        parameters_elem = ElementTree.SubElement(doc, 'parameters')
        parameters_elem.text = '\n'
        parameters_elem.tail = '\n'

        parameters = sorted(self.description.parameters, key=lambda p: p.name)
        parameter_values = dict(
            (p.name, p.value) for p in self.parameter_values)

        for parameter_name, value in sorted(self.parameter_values.items()):
            if parameter.hidden:
                continue

            value = parameter_values.get(parameter.name, parameter.default)

            parameter_elem = ElementTree.SubElement(
                parameters_elem, 'parameter', name=parameter.name)
            parameter_elem.text = parameter.to_string(value)
            parameter_elem.tail = '\n'

        tree = ElementTree.ElementTree(doc)
        buf = io.BytesIO()
        tree.write(buf, encoding='utf-8', xml_declaration=True)
        return buf.getvalue()
