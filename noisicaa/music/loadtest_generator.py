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
import random
import urllib.parse
from typing import cast, Any, Dict, List, Tuple, Type, TypeVar

import fastjsonschema

from noisicaa import audioproc
from noisicaa import value_types
from noisicaa.instr import soundfont
from . import model_base
from . import graph
from . import project as project_lib

logger = logging.getLogger(__name__)


def get_integer(spec: object) -> int:
    if isinstance(spec, int):
        return spec
    if isinstance(spec, dict) and spec.get('type') == 'randint':
        return random.randint(spec['min'], spec['max'] + 1)
    raise ValueError(spec)


node_generators = {}  # type: Dict[str, Type[NodeGenerator]]

class NodeGeneratorMeta(type):
    def __new__(mcs, name: str, parents: Any, dct: Dict[str, Any]) -> Any:
        gen = cast(Type['NodeGenerator'], super().__new__(mcs, name, parents, dct))
        if gen.SPEC_TYPE is not None:
            gen.SPEC_SCHEMA['properties']['type'] = {
                'type': 'string',
                'const': gen.SPEC_TYPE,
            }
            assert gen.SPEC_TYPE not in node_generators
            node_generators[gen.SPEC_TYPE] = gen
        return gen


class NodeGenerator(object, metaclass=NodeGeneratorMeta):
    SPEC_TYPE = None  # type: str
    SPEC_SCHEMA = None  # type: Dict[str, Any]

    def __init__(self, project: project_lib.BaseProject, spec: Dict[str, Any]) -> None:
        assert spec['type'] == self.SPEC_TYPE
        self.project = project
        self.spec = spec

    @property
    def master_mixer_node(self) -> graph.BaseNode:
        for node in self.project.nodes:
            if node.description.uri == 'builtin://mixer' and node.name == 'Master':
                return node
        raise AssertionError

    def create(self, num: int, pos: value_types.Pos2F) -> None:
        raise NotImplementedError


class ScoreTrackGenerator(NodeGenerator):
    SPEC_TYPE = 'builtin://score-track'
    SPEC_SCHEMA = {
        'properties': {
        },
    }  # type: Dict[str, Any]

    instruments = None  # type: List[Tuple[str, str]]

    @classmethod
    def get_instrument(cls) -> Tuple[str, str]:
        if cls.instruments is None:
            path = '/usr/share/sounds/sf2/FluidR3_GM.sf2'
            sfont = soundfont.SoundFont()
            sfont.parse(path)
            cls.instruments = []
            for preset in sfont.presets:
                uri = urllib.parse.urlunparse((
                    'sf2',
                    None,
                    urllib.parse.quote(path),
                    None,
                    urllib.parse.urlencode(
                        [('bank', str(preset.bank)), ('preset', str(preset.preset))],
                        True),
                    None))
                cls.instruments.append((preset.name, uri))

        return random.choice(cls.instruments)

    def create(self, num: int, pos: value_types.Pos2F) -> None:
        mixer_node = self.project.create_node(
            'builtin://mixer',
            name='Track #%d' % num,
            graph_pos=pos)
        mixer_node.set_control_value('gain', -10.0 * random.random())
        mixer_node.set_control_value('pan', 2.0 * random.random() - 1.0)
        self.project.create_node_connection(
            mixer_node, 'out:left',
            self.master_mixer_node, 'in:left')
        self.project.create_node_connection(
            mixer_node, 'out:right',
            self.master_mixer_node, 'in:right')

        from noisicaa.builtin_nodes.instrument import model as instrument

        instr_node = cast(
            instrument.Instrument,
            self.project.create_node(
                'builtin://instrument',
                graph_pos=pos - value_types.Pos2F(400, 0)))
        instr_node.name, instr_node.instrument_uri = self.get_instrument()
        self.project.create_node_connection(
            instr_node, 'out:left',
            mixer_node, 'in:left')
        self.project.create_node_connection(
            instr_node, 'out:right',
            mixer_node, 'in:right')

        from noisicaa.builtin_nodes.score_track import model as score_track

        track_node = cast(
            score_track.ScoreTrack,
            self.project.create_node(
                'builtin://score-track',
                name='Track #%d' % num,
                num_measures=0,
                graph_pos=pos - value_types.Pos2F(800, 0)))
        self.project.create_node_connection(
            track_node, 'out',
            instr_node, 'in')

        note_durations = (
            [audioproc.MusicalDuration(1, 4)] * 10
            + [audioproc.MusicalDuration(1, 8)] * 7
            + [audioproc.MusicalDuration(1, 16)] * 5
            + [audioproc.MusicalDuration(1, 32)] * 2
            + [audioproc.MusicalDuration(1, 2)] * 2
            + [audioproc.MusicalDuration(1, 1)] * 1
        )

        while track_node.duration < self.project.duration:
            measure = cast(score_track.ScoreMeasure, track_node.append_measure())
            duration_left = measure.duration
            while duration_left > audioproc.MusicalDuration(0, 1):
                durations = [d for d in note_durations if d <= duration_left]
                if not durations:
                    break

                note = measure.create_note(
                    index=len(measure.notes),
                    pitch=value_types.Pitch.from_midi(max(30, min(90, int(random.gauss(60, 5))))),
                    duration=random.choice(durations))

                duration_left -= note.duration


SPEC_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-07/schema',

    'definitions': {
        'numspec': {
            'oneOf': [{
                'type': 'integer',
            }, {
                'type': 'object',
                'properties': {
                    'type': {
                        'type': 'string',
                        'const': 'randint',
                    },
                    'min': {
                        'type': 'integer',
                    },
                    'max': {
                        'type': 'integer',
                    },
                },
                'required': ['min', 'max'],
                'additionalProperties': 'False',
            }],
        },

        'track': {
            'type': 'object',
            'properties': {
                'type': {
                    'type': 'string',
                },
                'count': {'$ref': '#/definitions/numspec'},
            },
            'oneOf': [
                ScoreTrackGenerator.SPEC_SCHEMA,
            ],
        },
    },

    'type': 'object',
    'properties': {
        'bpm': {'$ref': '#/definitions/numspec'},
        'tracks': {
            'type': 'array',
            'minItems': 0,
            'items': {'$ref': '#/definitions/track'},
        },
    },
    'additionalProperties': False,
}

validate_spec = fastjsonschema.compile(SPEC_SCHEMA)


PRESETS = {
    'default': {
        'bpm': 100,
        'tracks': [{
            'type': 'builtin://score-track',
            'count': 1,
        }],
    },
    '10 Score Tracks': {
        'bpm': {
            'type': 'randint',
            'min': 80,
            'max': 180,
        },
        'tracks': [{
            'type': 'builtin://score-track',
            'count': 10,
        }],
    },
}


PROJECT = TypeVar('PROJECT', bound=project_lib.BaseProject)
def create_loadtest_project(
        *,
        spec: dict,
        pool: model_base.Pool,
        project_cls: Type[PROJECT],
        **kwargs: Any
) -> PROJECT:
    project = pool.create(project_cls, **kwargs)
    pool.set_root(project)
    fill_project(project, spec)
    return project


def fill_project(project: project_lib.BaseProject, spec: dict) -> None:
    validate_spec(spec)

    project.bpm = get_integer(spec.get('bpm', 120))

    system_out_node = project.system_out_node

    master_mixer_node = project.create_node(
        'builtin://mixer',
        name='Master',
        graph_pos=system_out_node.graph_pos - value_types.Pos2F(400, 0))
    master_mixer_node.set_control_value('gain', -50.0)
    project.create_node_connection(
        master_mixer_node, 'out:left',
        system_out_node, 'in:left')
    project.create_node_connection(
        master_mixer_node, 'out:right',
        system_out_node, 'in:right')

    track_pos = master_mixer_node.graph_pos - value_types.Pos2F(800, 0)
    track_num = 1

    for track_spec in spec.get('tracks', []):
        track_type = track_spec['type']
        gen_cls = node_generators[track_type]
        gen = gen_cls(project, track_spec)

        count = get_integer(track_spec.get('count', 1))

        for _ in range(count):
            gen.create(track_num, track_pos)
            track_pos += value_types.Pos2F(0, 200)
            track_num += 1
