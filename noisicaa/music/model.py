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
import typing
from typing import cast, Any

from noisicaa import core
from noisicaa import model_base

if typing.TYPE_CHECKING:
    from . import project as project_lib

logger = logging.getLogger(__name__)


class ObjectBase(model_base.ObjectBase):
    _pool = None  # type: project_lib.Pool

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.object_changed = core.Callback[model_base.PropertyChange]()

    def property_changed(self, change: model_base.PropertyChange) -> None:
        super().property_changed(change)
        callback = getattr(self, change.prop_name + '_changed')
        callback.call(change)
        self.object_changed.call(change)
        self._pool.model_changed.call(change)

    @property
    def parent(self) -> 'ObjectBase':
        return cast(ObjectBase, super().parent)

    @property
    def project(self) -> 'project_lib.Project':
        return cast('project_lib.Project', self._pool.root)

    @property
    def attached_to_project(self) -> bool:
        raise NotImplementedError


class ProjectChild(ObjectBase):
    @property
    def attached_to_project(self) -> bool:
        if not self.is_attached:
            return None
        return self.parent.attached_to_project
