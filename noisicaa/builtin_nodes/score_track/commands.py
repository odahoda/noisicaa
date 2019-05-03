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

from typing import Tuple

from noisicaa import audioproc
from noisicaa import value_types
from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2
from . import model


def update(
        track: model.ScoreTrack, *,
        set_transpose_octaves: int = None
) -> music.Command:
    cmd = music.Command(command='update_score_track')
    pb = cmd.Extensions[commands_registry_pb2.update_score_track]
    pb.track_id = track.id
    if set_transpose_octaves is not None:
        pb.set_transpose_octaves = set_transpose_octaves
    return cmd

def update_measure(
        measure: model.ScoreMeasure, *,
        set_clef: value_types.Clef = None,
        set_key_signature: value_types.KeySignature = None
) -> music.Command:
    cmd = music.Command(command='update_score_measure')
    pb = cmd.Extensions[commands_registry_pb2.update_score_measure]
    pb.measure_id = measure.id
    if set_clef is not None:
        pb.set_clef.CopyFrom(set_clef.to_proto())
    if set_key_signature is not None:
        pb.set_key_signature.CopyFrom(set_key_signature.to_proto())
    return cmd

def create_note(
        measure: model.ScoreMeasure, *,
        idx: int,
        pitch: value_types.Pitch,
        duration: audioproc.MusicalDuration
) -> music.Command:
    cmd = music.Command(command='create_note')
    pb = cmd.Extensions[commands_registry_pb2.create_note]
    pb.measure_id = measure.id
    pb.idx = idx
    pb.pitch.CopyFrom(pitch.to_proto())
    pb.duration.CopyFrom(duration.to_proto())
    return cmd

def update_note(
        note: model.Note, *,
        set_pitch: value_types.Pitch = None,
        add_pitch: value_types.Pitch = None,
        remove_pitch: int = None,
        set_duration: audioproc.MusicalDuration = None,
        set_dots: int = None,
        set_tuplet: int = None,
        set_accidental: Tuple[int, str] = None,
        transpose: int = None,
) -> music.Command:
    cmd = music.Command(command='update_note')
    pb = cmd.Extensions[commands_registry_pb2.update_note]
    pb.note_id = note.id
    if set_pitch is not None:
        pb.set_pitch.CopyFrom(set_pitch.to_proto())
    if add_pitch is not None:
        pb.add_pitch.CopyFrom(add_pitch.to_proto())
    if remove_pitch is not None:
        pb.remove_pitch = remove_pitch
    if set_duration is not None:
        pb.set_duration.CopyFrom(set_duration.to_proto())
    if set_dots is not None:
        pb.set_dots = set_dots
    if set_tuplet is not None:
        pb.set_tuplet = set_tuplet
    if set_accidental is not None:
        pb.set_accidental.pitch_idx = set_accidental[0]
        pb.set_accidental.accidental = set_accidental[1]
    if transpose is not None:
        pb.transpose = transpose
    return cmd

def delete_note(note: model.Note) -> music.Command:
    cmd = music.Command(command='delete_note')
    pb = cmd.Extensions[commands_registry_pb2.delete_note]
    pb.note_id = note.id
    return cmd
