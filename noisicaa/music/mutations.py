#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

import logging

from noisicaa import core

logger = logging.getLogger(__name__)


class Mutation(object):
    def _prop2tuple(self, obj, prop):
        value = getattr(obj, prop.name, None)
        if isinstance(prop, core.ObjectProperty):
            return (
                prop.name,
                'obj',
                value.id if value is not None else None)

        elif isinstance(prop, core.ObjectReferenceProperty):
            return (
                prop.name,
                'objref',
                value.id if value is not None else None)

        elif isinstance(prop, core.ObjectListProperty):
            return (
                prop.name,
                'objlist',
                [v.id for v in value])

        elif isinstance(prop, core.ListProperty):
            return (prop.name, 'list', list(value))

        else:
            return (prop.name, 'scalar', value)


class SetProperties(Mutation):
    def __init__(self, obj, properties):
        self.id = obj.id
        self.properties = []
        for prop_name in properties:
            prop = obj.get_property(prop_name)
            self.properties.append(self._prop2tuple(obj, prop))

    def __str__(self):
        return '<SetProperties id="%s" %s>' % (
            self.id,
            ' '.join(
                '%s=%s:%r' % (p, t, v)
                for p, t, v in self.properties))


class AddObject(Mutation):
    def __init__(self, obj):
        self.id = obj.id
        self.cls = obj.SERIALIZED_CLASS_NAME or obj.__class__.__name__
        self.properties = []
        for prop in obj.list_properties():
            if prop.name == 'id':
                continue
            self.properties.append(self._prop2tuple(obj, prop))

    def __str__(self):
        return '<AddObject id=%s cls=%s %s>' % (
            self.id, self.cls,
            ' '.join(
                '%s=%s:%r' % (p, t, v)
                for p, t, v in self.properties))
    __repr__ = __str__


class ListInsert(Mutation):
    def __init__(self, obj, prop_name, index, value):
        self.id = obj.id
        self.prop_name = prop_name
        self.index = index
        prop = obj.get_property(prop_name)
        if isinstance(prop, core.ObjectListProperty):
            self.value_type = 'obj'
            self.value = value.id
        else:
            self.value_type = 'scalar'
            self.value = value

    def __str__(self):
        return '<ListInsert id=%s prop=%s index=%d value=%s:%s>' % (
            self.id, self.prop_name, self.index,
            self.value_type, self.value)
    __repr__ = __str__


class ListDelete(Mutation):
    def __init__(self, obj, prop_name, index):
        self.id = obj.id
        self.prop_name = prop_name
        self.index = index

    def __str__(self):
        return '<ListDelete id=%s prop=%s index=%d>' % (
            self.id, self.prop_name, self.index)


