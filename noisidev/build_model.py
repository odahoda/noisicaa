#!/usr/bin/env python3

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

import argparse
import logging
import os
import os.path
import sys
import textwrap

from google.protobuf import text_format
import jinja2

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRCDIR = ROOTDIR
LIBDIR = os.path.join(ROOTDIR, 'build')
sys.path.insert(0, LIBDIR)

from noisidev import model_desc_pb2


class ModelBuilder(object):
    def __init__(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument('model_desc', type=str)
        parser.add_argument('--output', '-o', type=str)
        parser.add_argument(
            '--log-level',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            default='critical',
            help="Minimum level for log messages written to STDERR.")
        self.args = parser.parse_args(argv[1:])

        assert self.args.model_desc.endswith('.desc.pb')

        self.model_desc = model_desc_pb2.ModelDescription()
        with open(self.args.model_desc, 'r', encoding='utf-8') as fp:
            text_format.Merge(fp.read(), self.model_desc)

        self.model_mod = '.'.join(self.args.model_desc.split('/')[:-1]) + '.model'

        self.imports = set()
        self.typing_imports = set()
        self.proto_imports = set()

    def build(self):
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        logging.basicConfig(
            format='%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s',
            level={
                'debug': logging.DEBUG,
                'info': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR,
                'critical': logging.CRITICAL,
            }[self.args.log_level])

        wrapped_proto_map = {
            'noisicaa.value_types.Pitch': 'noisicaa/value_types/value_types.proto:noisicaa.pb.Pitch',
            'noisicaa.value_types.Clef': 'noisicaa/value_types/value_types.proto:noisicaa.pb.Clef',
            'noisicaa.value_types.KeySignature': 'noisicaa/value_types/value_types.proto:noisicaa.pb.KeySignature',
            'noisicaa.audioproc.MusicalDuration': "noisicaa/audioproc/public/musical_time.proto:noisicaa.pb.MusicalDuration",
            'noisicaa.audioproc.MusicalTime': "noisicaa/audioproc/public/musical_time.proto:noisicaa.pb.MusicalTime"
        }

        for cls in self.model_desc.classes:
            for super_cls in cls.super_class:
                if '.' in super_cls:
                    self.imports.add('.'.join(super_cls.split('.')[:-1]))

            for prop in cls.properties:
                if not prop.HasField('wrapped_proto_type') and prop.type in {
                        model_desc_pb2.PropertyDescription.WRAPPED_PROTO,
                        model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST,
                }:
                    prop.wrapped_proto_type = wrapped_proto_map[prop.wrapped_type]
                if prop.HasField('wrapped_type') and '.' in prop.wrapped_type:
                    self.imports.add('.'.join(prop.wrapped_type.split('.')[:-1]))
                if prop.HasField('wrapped_proto_type') and ':' in prop.wrapped_proto_type:
                    self.proto_imports.add(prop.wrapped_proto_type.split(':')[0])
                if prop.type == model_desc_pb2.PropertyDescription.OBJECT_LIST:
                    self.typing_imports.add(self.model_mod)
                if prop.type == model_desc_pb2.PropertyDescription.OBJECT_REF:
                    self.imports.add('.'.join(prop.obj_type.split('.')[:-1]))

        env = jinja2.Environment()
        env.filters['py_type'] = self.py_type
        env.filters['proto_type'] = self.proto_type
        env.filters['proto_mod'] = self.proto_mod
        env.filters['has_setter'] = self.has_setter
        env.filters['prop_cls'] = self.prop_cls
        env.filters['prop_cls_type'] = self.prop_cls_type
        env.filters['change_cls'] = self.change_cls

        with open(self.model_desc.template, 'r', encoding='utf-8') as fp:
            model_py_tmpl = env.from_string(fp.read())
        model_py_output = model_py_tmpl.render(
            desc=self.model_desc,
            imports=list(sorted(self.imports)),
            typing_imports=list(sorted(self.typing_imports)),
        )
        model_py_path = os.path.join(
            self.args.output,
            os.path.dirname(self.args.model_desc),
            '_' + os.path.basename(self.args.model_desc)[:-8] + '.py')
        with open(model_py_path, 'w', encoding='utf-8') as fp:
            fp.write(model_py_output)

        model_proto_tmpl = env.from_string(textwrap.dedent('''\
            syntax = "proto2";
            {%- for path in proto_imports %}
            import "{{path}}";
            {%- endfor %}
            package noisicaa.pb;
            {% for cls in desc.classes %}
            message {{cls.name}} {
            {%- for prop in cls.properties %}
            {%- if prop.HasField('proto_enum_name') %}
              enum {{prop.proto_enum_name}} {
            {%- for field in prop.proto_enum_fields %}
                {{field.name}} = {{field.value}};
            {%- endfor %}
              }
            {%- endif %}
              {{prop|proto_mod}} {{prop|proto_type}} {{prop.name}} = {{prop.proto_id}};
            {%- endfor %}
            }
            {% endfor %}
            '''))
        model_proto_output = model_proto_tmpl.render(
            desc=self.model_desc,
            proto_imports=list(sorted(self.proto_imports)),
        )
        model_proto_path = os.path.join(
            self.args.output,
            os.path.dirname(self.args.model_desc),
            os.path.basename(self.args.model_desc)[:-8] + '.proto')
        with open(model_proto_path, 'w', encoding='utf-8') as fp:
            fp.write(model_proto_output)

    def prop_cls(self, prop):
        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_LIST:
            return 'ObjectListProperty'
        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_REF:
            return 'ObjectReferenceProperty'
        if prop.type == model_desc_pb2.PropertyDescription.WRAPPED_PROTO:
            return 'WrappedProtoProperty'
        if prop.type == model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST:
            return 'WrappedProtoListProperty'
        return 'Property'

    def prop_cls_type(self, prop):
        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_LIST:
            return prop.obj_type
        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_REF:
            return prop.obj_type
        if prop.type == model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST:
            return prop.wrapped_type
        return self.py_type(prop)

    def change_cls(self, prop):
        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_LIST:
            return 'PropertyListChange[%r]' % prop.obj_type
        if prop.type == model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST:
            return 'PropertyListChange[%r]' % prop.wrapped_type
        return 'PropertyChange[%s]' % self.py_type(prop)

    def py_type(self, prop):
        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_LIST:
            return 'typing.MutableSequence[%r]' % (self.model_mod + '.' + prop.obj_type)

        if prop.type == model_desc_pb2.PropertyDescription.OBJECT_REF:
            return repr(prop.obj_type)

        if prop.type == model_desc_pb2.PropertyDescription.WRAPPED_PROTO:
            return prop.wrapped_type

        if prop.type == model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST:
            return 'typing.MutableSequence[%r]' % (prop.wrapped_type)

        return {
            model_desc_pb2.PropertyDescription.STRING: 'str',
            model_desc_pb2.PropertyDescription.INT32: 'int',
            model_desc_pb2.PropertyDescription.UINT32: 'int',
            model_desc_pb2.PropertyDescription.FLOAT: 'float',
            model_desc_pb2.PropertyDescription.BOOL: 'bool',
            model_desc_pb2.PropertyDescription.PROTO_ENUM: 'int',
        }[prop.type]

    def proto_mod(self, prop):
        if prop.type in {
                model_desc_pb2.PropertyDescription.OBJECT_LIST,
                model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST,
        }:
            return 'repeated'
        return 'optional'

    def proto_type(self, prop):
        if prop.type in {
                model_desc_pb2.PropertyDescription.WRAPPED_PROTO,
                model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST,
        }:
            return prop.wrapped_proto_type.split(':')[-1]

        if prop.type == model_desc_pb2.PropertyDescription.PROTO_ENUM:
            return prop.proto_enum_name

        return {
            model_desc_pb2.PropertyDescription.STRING: 'string',
            model_desc_pb2.PropertyDescription.FLOAT: 'float',
            model_desc_pb2.PropertyDescription.INT32: 'int32',
            model_desc_pb2.PropertyDescription.UINT32: 'uint32',
            model_desc_pb2.PropertyDescription.BOOL: 'bool',
            model_desc_pb2.PropertyDescription.OBJECT_REF: 'uint64',
            model_desc_pb2.PropertyDescription.OBJECT_LIST: 'uint64',
        }[prop.type]

    def has_setter(self, prop):
        return prop.type not in {
            model_desc_pb2.PropertyDescription.OBJECT_LIST,
            model_desc_pb2.PropertyDescription.WRAPPED_PROTO_LIST,
        }


if __name__ == '__main__':
    ModelBuilder(sys.argv).build()
    sys.exit(0)
