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

# Be less picky for generated code:
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long

import typing

from noisicaa import core
from noisicaa import music
from noisicaa.builtin_nodes import model_registry_pb2
{%- for mod in imports %}
import {{mod}}
{%- endfor %}

{% if typing_imports %}
if typing.TYPE_CHECKING:
{%- for mod in typing_imports %}
    import {{mod}}
{% endfor %}
{% endif %}

{% for cls in desc.classes %}
class {{cls.name}}({{cls.super_class|join(', ')}}):  # pylint: disable=abstract-method
    class {{cls.name}}Spec(music.ObjectSpec):
        proto_type = '{{cls.proto_ext_name}}'
        proto_ext = model_registry_pb2.{{cls.proto_ext_name}}
{% for prop in cls.properties %}
        {{prop.name}} = music.{{prop|prop_cls}}({{prop|prop_cls_type}}{% if prop.HasField("allow_none") %}, allow_none={{prop.allow_none}}{% endif %}{% if prop.HasField("default") %}, default={{prop.default}}{% endif %})
{%- endfor %}

    def __init__(self, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
{% for prop in cls.properties %}
        self.change_callbacks['{{prop.name}}'] = core.Callback[music.{{prop|change_cls}}]()
{%- endfor %}

{% for prop in cls.properties %}
    def _get_{{prop.name}}(self) -> {{prop|py_type}}:
        return self.get_property_value('{{prop.name}}')
{% if not prop|has_setter %}

    {{prop.name}} = property(_get_{{prop.name}})

{% else %}

    def _set_{{prop.name}}(self, value: {{prop|py_type}}) -> None:
        self.set_property_value('{{prop.name}}', value)

    {{prop.name}} = property(_get_{{prop.name}}, _set_{{prop.name}})

{% endif %}

    @property
    def {{prop.name}}_changed(self) -> core.Callback[music.{{prop|change_cls}}]:
        return self.change_callbacks['{{prop.name}}']
{% endfor %}

{% endfor %}
