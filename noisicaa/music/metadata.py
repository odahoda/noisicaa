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

import logging
from typing import Any

from noisicaa import core
from noisicaa import model_base
from . import model_pb2
from . import model

logger = logging.getLogger(__name__)


class Metadata(model.ProjectChild):
    class MetadataSpec(model_base.ObjectSpec):
        proto_type = 'metadata'
        proto_ext = model_pb2.metadata

        author = model_base.Property(str, allow_none=True)
        license = model_base.Property(str, allow_none=True)
        copyright = model_base.Property(str, allow_none=True)
        created = model_base.Property(int, allow_none=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.author_changed = core.Callback[model_base.PropertyChange[str]]()
        self.license_changed = core.Callback[model_base.PropertyChange[str]]()
        self.copyright_changed = core.Callback[model_base.PropertyChange[str]]()
        self.created_changed = core.Callback[model_base.PropertyChange[int]]()

    @property
    def author(self) -> str:
        return self.get_property_value('author')

    @author.setter
    def author(self, value: str) -> None:
        self.set_property_value('author', value)

    @property
    def license(self) -> str:
        return self.get_property_value('license')

    @license.setter
    def license(self, value: str) -> None:
        self.set_property_value('license', value)

    @property
    def copyright(self) -> str:
        return self.get_property_value('copyright')

    @copyright.setter
    def copyright(self, value: str) -> None:
        self.set_property_value('copyright', value)

    @property
    def created(self) -> int:
        return self.get_property_value('created')

    @created.setter
    def created(self, value: int) -> None:
        self.set_property_value('created', value)
