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
from typing import cast, Any, Iterator, Iterable

from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import value_types
from . import node_description
from . import processor_pb2
from . import _model

logger = logging.getLogger(__name__)


class MidiLooperPatch(_model.MidiLooperPatch):
    @property
    def midi_looper(self) -> 'MidiLooper':
        return cast(MidiLooper, self.parent)

    def set_events(self, events: Iterable[value_types.MidiEvent]) -> None:
        self.events.clear()
        self.events.extend(events)
        self.midi_looper.update_spec()


class MidiLooper(_model.MidiLooper):
    def create(self, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.duration = audioproc.MusicalDuration(8, 4)
        self.patches.append(self._pool.create(MidiLooperPatch))

    def setup(self) -> None:
        super().setup()

        self.duration_changed.add(lambda _: self.update_spec())

        # TODO: this causes a large number of spec updates when the patch is populated (one for each
        # event added). It would be better to schedule a single update at the end of the mutation.
        self.patches[0].object_changed.add(lambda _: self.update_spec())

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        yield from super().get_initial_parameter_mutations()
        yield self.__get_spec_mutation()

    def update_spec(self) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                self.__get_spec_mutation())

    def __get_spec_mutation(self) -> audioproc.Mutation:
        params = audioproc.NodeParameters()
        spec = params.Extensions[processor_pb2.midi_looper_spec]
        spec.duration.CopyFrom(self.duration.to_proto())
        for event in self.patches[0].events:
            pb_event = spec.events.add()
            pb_event.CopyFrom(event.to_proto())

        return audioproc.Mutation(
            set_node_parameters=audioproc.SetNodeParameters(
                node_id=self.pipeline_node_id,
                parameters=params))

    @property
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.MidiLooperDescription)
        return node_desc

    def set_duration(self, duration: audioproc.MusicalDuration) -> None:
        self.duration = duration
