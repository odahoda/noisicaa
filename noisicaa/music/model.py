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
# pylint: disable=reimported
# pylint: disable=wrong-import-order

import typing

from noisicaa import core
from . import model_base
from . import project_pb2
{%- for mod in imports %}
import {{mod}}
{%- endfor %}

{% if typing_imports %}
if typing.TYPE_CHECKING:
{%- for mod in typing_imports %}
    import {{mod}}
{% endfor %}
{% endif %}

ObjectBase = model_base.ObjectBase

{% for cls in desc.classes %}
class {{cls.name}}({{cls.super_class|join(', ')}}):  # pylint: disable=abstract-method
    class {{cls.name}}Spec(model_base.ObjectSpec):
{%- if not cls.is_abstract %}
        proto_type = '{{cls.proto_ext_name}}'
{%- endif %}
        proto_ext = project_pb2.{{cls.proto_ext_name}}
{% for prop in cls.properties %}
        {{prop.name}} = model_base.{{prop|prop_cls}}({{prop|prop_cls_type}}{% if prop.HasField("allow_none") %}, allow_none={{prop.allow_none}}{% endif %}{% if prop.HasField("default") %}, default={{prop.default}}{% endif %})
{%- endfor %}

{% if cls.properties %}
    def __init__(self, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
{% for prop in cls.properties %}
        self.change_callbacks['{{prop.name}}'] = core.Callback[model_base.{{prop|change_cls}}]()
{%- endfor %}
{% endif %}

{% for prop in cls.properties %}
    @property
    def {{prop.name}}(self) -> {{prop|py_type}}:
        return self.get_property_value('{{prop.name}}')
{% if prop|has_setter %}

    @{{prop.name}}.setter
    def {{prop.name}}(self, value: {{prop|py_type}}) -> None:
        self._validate_{{prop.name}}(value)
        self.set_property_value('{{prop.name}}', value)

    def _validate_{{prop.name}}(self, value: {{prop|py_type}}) -> None:
        pass
{% endif %}

    @property
    def {{prop.name}}_changed(self) -> core.Callback[model_base.{{prop|change_cls}}]:
        return self.change_callbacks['{{prop.name}}']
{% endfor %}

{% endfor %}
