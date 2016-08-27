#!/usr/bin/python3

import logging
import os
import os.path
from xml.etree import ElementTree

from noisicaa import core
from noisicaa import constants
from noisicaa import node_db

logger = logging.getLogger(__name__)


class NodeDB(object):
    def __init__(self):
        self._nodes = {}
        self.listeners = core.CallbackRegistry()

    def setup(self):
        self.load_csound_nodes()

    def cleanup(self):
        pass

    def initial_mutations(self):
        for uri, node_description in sorted(self._nodes.items()):
            yield node_db.AddNodeDescription(uri, node_description)

    def start_scan(self):
        pass

    def load_csound_nodes(self):
        rootdir = os.path.join(constants.DATA_DIR, 'csound')
        for dirpath, dirnames, filenames in os.walk(rootdir):
            for filename in filenames:
                if not filename.endswith('.csnd'):
                    continue

                uri = 'builtin://csound/%s' % filename[:-5]
                assert uri not in self._nodes

                path = os.path.join(rootdir, filename)
                logger.info("Loading csound node %s from %s", uri, path)

                tree = ElementTree.parse(path)
                root = tree.getroot()
                assert root.tag == 'csound'

                ports = []
                for port_elem in root.find('ports').findall('port'):
                    port_cls = {
                        'audio': node_db.AudioPortDescription,
                        'events': node_db.EventPortDescription,
                    }[port_elem.get('type')]
                    direction = {
                        'input': node_db.PortDirection.Input,
                        'output': node_db.PortDirection.Output,
                    }[port_elem.get('direction')]

                    kwargs = {}
                    drywet_elem = port_elem.find('drywet')
                    if drywet_elem is not None:
                        kwargs['drywet_port'] = drywet_elem.get('port')
                        kwargs['drywet_default'] = drywet_elem.get('default')

                    bypass_elem = port_elem.find('bypass')
                    if bypass_elem is not None:
                        kwargs['bypass_port'] = bypass_elem.get('port')

                    port_desc = port_cls(
                        name=port_elem.get('name'),
                        direction=direction,
                        **kwargs)
                    ports.append(port_desc)

                parameters = []
                for parameter_elem in root.find('parameters').findall('parameter'):
                    parameter_cls = {
                        'float': node_db.FloatParameterDescription,
                    }[parameter_elem.get('type')]

                    kwargs = {}
                    kwargs['name'] = parameter_elem.get('name')
                    kwargs['display_name'] = ''.join(
                        parameter_elem.find('display-name').itertext())


                    if parameter_elem.get('type') == 'float':
                        kwargs['min'] = float(parameter_elem.get('min'))
                        kwargs['max'] = float(parameter_elem.get('max'))
                        kwargs['default'] = float(parameter_elem.get('default'))

                    parameter_desc = parameter_cls(**kwargs)
                    parameters.append(parameter_desc)


                code = ''.join(root.find('code').itertext())
                code = code.strip() + '\n'
                parameters.append(
                    node_db.InternalParameterDescription(
                        name='code', value=code))

                display_name = ''.join(
                    root.find('display-name').itertext())

                node_desc = node_db.UserNodeDescription(
                    display_name=display_name,
                    node_cls='csound_filter',
                    ports=ports,
                    parameters=parameters)

                self._nodes[uri] = node_desc
