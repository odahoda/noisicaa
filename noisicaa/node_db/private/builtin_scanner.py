#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
from typing import Iterator, Tuple

from noisicaa import node_db

from . import scanner

logger = logging.getLogger(__name__)


class Builtins(object):
    TrackMixerDescription = node_db.NodeDescription(
        display_name='Mixer',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.TRACK_MIXER,
        ),
        ports=[
            node_db.PortDescription(
                name='in:left',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='in:right',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='gain',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.KRATE_CONTROL,
            ),
            node_db.PortDescription(
                name='muted',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.KRATE_CONTROL,
            ),
            node_db.PortDescription(
                name='pan',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.KRATE_CONTROL,
            ),
        ]
    )

    SampleScriptDescription = node_db.NodeDescription(
        display_name='Sample Script',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.SAMPLE_SCRIPT,
        ),
        ports=[
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )

    EventSourceDescription = node_db.NodeDescription(
        display_name='Events',
        type=node_db.NodeDescription.EVENT_SOURCE,
        ports=[
            node_db.PortDescription(
                name='out',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.EVENTS,
            ),
        ]
    )

    CVGeneratorDescription = node_db.NodeDescription(
        display_name='Control Value',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.CV_GENERATOR,
        ),
        ports=[
            node_db.PortDescription(
                name='out',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.ARATE_CONTROL,
            ),
        ]
    )

    PianoRollDescription = node_db.NodeDescription(
        display_name='Piano Roll',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.PIANOROLL,
        ),
        ports=[
            node_db.PortDescription(
                name='out',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.EVENTS,
            ),
        ]
    )

    RealmSinkDescription = node_db.NodeDescription(
        display_name='Output',
        type=node_db.NodeDescription.REALM_SINK,
        ports=[
            node_db.PortDescription(
                name='in:left',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='in:right',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )

    ChildRealmDescription = node_db.NodeDescription(
        display_name='Child',
        type=node_db.NodeDescription.CHILD_REALM,
        ports=[
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )

    FluidSynthDescription = node_db.NodeDescription(
        display_name='FluidSynth',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.FLUIDSYNTH,
        ),
        ports=[
            node_db.PortDescription(
                name='in',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.EVENTS,
            ),
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )

    SamplePlayerDescription = node_db.NodeDescription(
        display_name='Sampler',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.SAMPLE_PLAYER,
        ),
        ports=[
            node_db.PortDescription(
                name='in',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.EVENTS,
            ),
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )

    SoundFileDescription = node_db.NodeDescription(
        display_name='Sound Player',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.SOUND_FILE,
        ),
        ports=[
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )

    CustomCSoundDescription = node_db.NodeDescription(
        display_name='Custom CSound',
        type=node_db.NodeDescription.PROCESSOR,
        processor=node_db.ProcessorDescription(
            type=node_db.ProcessorDescription.CUSTOM_CSOUND,
        ),
        ports=[
            node_db.PortDescription(
                name='in:left',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='in:right',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='ctrl',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.ARATE_CONTROL,
            ),
            node_db.PortDescription(
                name='ev',
                direction=node_db.PortDescription.INPUT,
                type=node_db.PortDescription.EVENTS,
            ),
            node_db.PortDescription(
                name='out:left',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
            node_db.PortDescription(
                name='out:right',
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.AUDIO,
            ),
        ]
    )


class BuiltinScanner(scanner.Scanner):
    def scan(self) -> Iterator[Tuple[str, node_db.NodeDescription]]:
        yield ('builtin://track_mixer', Builtins.TrackMixerDescription)
        yield ('builtin://sample_script', Builtins.SampleScriptDescription)
        yield ('builtin://event_source', Builtins.EventSourceDescription)
        yield ('builtin://cvgenerator', Builtins.CVGeneratorDescription)
        yield ('builtin://pianoroll', Builtins.PianoRollDescription)
        yield ('builtin://sink', Builtins.RealmSinkDescription)
        yield ('builtin://child_realm', Builtins.ChildRealmDescription)
        yield ('builtin://fluidsynth', Builtins.FluidSynthDescription)
        yield ('builtin://sample_player', Builtins.SamplePlayerDescription)
        yield ('builtin://custom_csound', Builtins.CustomCSoundDescription)
        yield ('builtin://sound_file', Builtins.SoundFileDescription)
