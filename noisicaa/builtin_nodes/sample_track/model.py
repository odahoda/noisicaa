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

from typing import Any

from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import model
from noisicaa.builtin_nodes import model_registry_pb2
from . import node_description


class SampleRef(model.ProjectChild):
    class SampleRefSpec(model.ObjectSpec):
        proto_type = 'sample_ref'
        proto_ext = model_registry_pb2.sample_ref

        time = model.WrappedProtoProperty(audioproc.MusicalTime)
        sample = model.ObjectReferenceProperty(model.Sample)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = core.Callback[model.PropertyChange[audioproc.MusicalTime]]()
        self.sample_changed = core.Callback[model.PropertyChange[model.Sample]]()


class SampleTrack(model.Track):
    class SampleTrackSpec(model.ObjectSpec):
        proto_type = 'sample_track'
        proto_ext = model_registry_pb2.sample_track

        samples = model.ObjectListProperty(SampleRef)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.samples_changed = core.Callback[model.PropertyListChange[SampleRef]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.SampleTrackDescription
