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

from typing import Sequence

from noisicaa import audioproc
from noisicaa import model
from noisicaa import music
from noisicaa.builtin_nodes import commands_registry_pb2

def change_note(
        track_id: int, *,
        idx: int,
        pitch: model.Pitch = None,
        duration: audioproc.MusicalDuration = None,
        dots: int = None,
        tuplet: int = None
) -> music.Command:
    cmd = music.Command(target=track_id, command='change_note')
    pb = cmd.Extensions[commands_registry_pb2.change_note]  # type: ignore
    pb.idx = idx
    if pitch is not None:
        pb.pitch = str(pitch)
    if duration is not None:
        pb.duration.CopyFrom(duration.to_proto())
    if dots is not None:
        pb.dots = dots
    if tuplet is not None:
        pb.tuplet = tuplet
    return cmd

def insert_note(
        track_id: int, *, idx: int, pitch: model.Pitch, duration: audioproc.MusicalDuration
) -> music.Command:
    cmd = music.Command(target=track_id, command='insert_note')
    pb = cmd.Extensions[commands_registry_pb2.insert_note]  # type: ignore
    pb.idx = idx
    pb.pitch = str(pitch)
    pb.duration.CopyFrom(duration.to_proto())
    return cmd

def delete_note(
        track_id: int, *, idx: int) -> music.Command:
    cmd = music.Command(target=track_id, command='delete_note')
    pb = cmd.Extensions[commands_registry_pb2.delete_note]  # type: ignore
    pb.idx = idx
    return cmd

def add_pitch(
        track_id: int, *, idx: int, pitch: model.Pitch) -> music.Command:
    cmd = music.Command(target=track_id, command='add_pitch')
    pb = cmd.Extensions[commands_registry_pb2.add_pitch]  # type: ignore
    pb.idx = idx
    pb.pitch = str(pitch)
    return cmd

def remove_pitch(
        track_id: int, *, idx: int, pitch_idx: int) -> music.Command:
    cmd = music.Command(target=track_id, command='remove_pitch')
    pb = cmd.Extensions[commands_registry_pb2.remove_pitch]  # type: ignore
    pb.idx = idx
    pb.pitch_idx = pitch_idx
    return cmd

def set_clef(
        track_id: int, *,
        measure_ids: Sequence[int],
        clef: model.Clef
) -> music.Command:
    cmd = music.Command(target=track_id, command='set_clef')
    pb = cmd.Extensions[commands_registry_pb2.set_clef]  # type: ignore
    pb.measure_ids[:] = measure_ids
    pb.clef.CopyFrom(clef.to_proto())
    return cmd

def set_key_signature(
        track_id: int, *,
        measure_ids: Sequence[int],
        key_signature: model.KeySignature
) -> music.Command:
    cmd = music.Command(target=track_id, command='set_key_signature')
    pb = cmd.Extensions[commands_registry_pb2.set_key_signature]  # type: ignore
    pb.measure_ids[:] = measure_ids
    pb.key_signature.CopyFrom(key_signature.to_proto())
    return cmd

def set_accidental(
        track_id: int, *, idx: int, pitch_idx: int, accidental: str) -> music.Command:
    cmd = music.Command(target=track_id, command='set_accidental')
    pb = cmd.Extensions[commands_registry_pb2.set_accidental]  # type: ignore
    pb.idx = idx
    pb.pitch_idx = pitch_idx
    pb.accidental = accidental
    return cmd

def transpose_notes(
        track_id: int, *, note_ids: Sequence[int], half_notes: int) -> music.Command:
    cmd = music.Command(target=track_id, command='transpose_notes')
    pb = cmd.Extensions[commands_registry_pb2.transpose_notes]  # type: ignore
    pb.note_ids[:] = note_ids
    pb.half_notes = half_notes
    return cmd
