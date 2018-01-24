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
import re
import fractions
import collections

from noisicaa import audioproc
from noisicaa import music

logger = logging.getLogger('__name__')


class ImporterError(Exception):
    pass

class ParseError(ImporterError):
    pass


class ABCImporter(object):
    def __init__(self):
        self.state = 'start'
        self.fields = {}
        self.prev_field = None

        self.reference_number = None
        self.key = music.KeySignature('C major')
        self.unit_length = None
        self.meter = None
        self.tempo = None
        self.title = []
        self.composer = []
        self.lyrics = []
        self.origin = []
        self.file_url = []
        self.transcription = []

        self.decorations = {
            '~': 'roll',
            'H': 'fermata',
            'L': 'accent',
            'M': 'lowermordent',
            'O': 'coda',
            'P': 'uppermordent',
            'S': 'segno',
            'T': 'trill',
            'u': 'upbow',
            'v': 'downbow',
        }

        self.next_length_multiplier = fractions.Fraction(1)

        self.notes = []
        self.voices = collections.OrderedDict()
        self.current_voice = None

    def import_file(self, path, proj):
        with open(path, 'r') as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                line = line.rstrip()
                logger.debug("Parse line: %s", line)

                line = re.sub(r'%.*$', '', line)
                if line.strip() == '':
                    continue

                # State switches between file sections.
                if self.state in ('start', 'after-tune'):
                    if line.startswith('X:'):
                        logger.debug("Found tune header.")
                        self.state = 'tune'

                elif self.state == 'tune':
                    if line.strip() == '':
                        self.state = 'after-tune'

                if self.state == 'start':
                    if line.strip() != '':
                        logger.warning("Ignoring content before tune")

                elif self.state == 'after-tune':
                    if line.strip() != '':
                        logger.warning("Ignoring content after tune")

                elif self.state == 'tune':
                    if re.match(r'[A-Za-z\+]:$', line[:2]):
                        field = line[0]
                        contents = line[2:].strip()
                        self.parse_information_field(field, contents)
                    else:
                        self.parse_music(line)

        for voice in self.voices.values():
            proj.master_group.tracks.append(voice)
        proj.equalize_tracks()
        proj.bpm = self.tempo

    def parse_information_field(self, field, contents):
        if field == 'K':
            self.key = self.parse_key(contents)
        elif field == 'L':
            self.unit_length = self.parse_unit_length(contents)
        elif field == 'M':
            self.meter = contents
        elif field == 'Q':
            self.tempo = self.parse_tempo(contents)
        elif field == 'V':
            voice_id = contents.split()[0]
            if voice_id not in self.voices:
                self.voices[voice_id] = music.ScoreTrack(
                    name="Track %s" % voice_id, num_measures=0)
            self.current_voice = self.voices[voice_id]
        elif field == 'T':
            self.title.append(contents)
        elif field == 'C':
            self.composer.append(contents)
        elif field == 'X':
            self.reference_number = contents
        elif field == 'W':
            self.lyrics.append(contents)
        elif field == 'w':
            self.lyrics.append(contents)
        elif field in ('O', 'A'):
            self.origin.append(contents)
        elif field == 'F':
            self.file_url.append(contents)
        elif field == 'Z':
            self.transcription.append(contents)
        else:
            logger.warning("Ignoring unsupported information field %s", field)

        # logger.debug("Information field %c: %s", field, contents)
        # if field == '+':
        #     if self.prev_field is None:
        #         raise ParseError("Continuation doesn't continue anything.")
        #     self.fields[self.prev_field][-1] += ' ' + contents
        # else:
        #     self.fields.setdefault(field, []).append(contents)
        #     self.prev_field = field

    def parse_key(self, s):
        if len(s) == 1:
            return music.KeySignature(s.upper() + ' major')
        else:
            raise ImporterError("Key signature %s nor supported." % s)

    def parse_unit_length(self, s):
        return fractions.Fraction(s)

    def skip_whitespace(self, s):
        while len(s) > 0 and s[0].isspace():
            s = s[1:]
        return s

    quoted_string_start = '"'
    def parse_quoted_string(self, s):
        assert s[0] == '"'
        s = s[1:]

        value = ''
        while len(s) > 0 and s[0] != '"':
            value += s[0]
            s = s[1:]

        if len(s) == 0:
            raise ParseError("Unterminated string")

        assert s[0] == '"'
        s = s[1:]
        return value, s

    def parse_tempo(self, s):
        orig = s

        s = self.skip_whitespace(s)

        if len(s) > 0 and s[0] in self.quoted_string_start:
            _, s = self.parse_quoted_string(s)
            s = self.skip_whitespace(s)

        bases = []
        beats = None
        eq_seen = False

        while True:
            if len(s) > 0 and s[0] in self.length_start_chars:
                length, s = self.parse_length(s)
                s = self.skip_whitespace(s)

                if eq_seen:
                    beats = length
                else:
                    bases.append(length)

            elif len(s) > 0 and s[0] == '=':
                s = s[1:]
                s = self.skip_whitespace(s)
                eq_seen = True

            else:
                break

        s = self.skip_whitespace(s)

        if len(s) > 0 and s[0] in self.quoted_string_start:
            _, s = self.parse_quoted_string(s)
            s = self.skip_whitespace(s)

        if not eq_seen and len(bases) == 0:
            return 120

        if not eq_seen and len(bases) == 1:
            beats = bases.pop(0)

        if beats is None:
            raise ParseError("Malformed tempo %s" % orig)

        if len(bases) == 0:
            bases.append(fractions.Fraction(1, 4))
        base = sum(bases)

        return int(beats * 4 * base)

    def emit_note(self, note):
        self.notes.append(note)

    def emit_measure(self):
        measure = music.ScoreMeasure()
        measure.key_signature = self.key
        #measure.time_signature = music.TimeSignature(self.meter)
        for note in self.notes:
            measure.notes.append(note)
        self.notes = []

        if self.current_voice is None:
            assert '1' not in self.voices
            self.voices['1'] = music.ScoreTrack(
                name="Track 1", num_measures=0)
            self.current_voice = self.voices['1']

        self.current_voice.measures.append(measure)

    decoration_start_chars = 'HIJKLMNOPQRSTUVWhijklmnopqrstuvw.~+!'
    def parse_decoration(self, line):
        if len(line) > 0 and line[0] in 'HIJKLMNOPQRSTUVWhijklmnopqrstuvw~':
            try:
                decoration = self.decorations[line[0]]
            except KeyError:
                raise ParseError("Undefined symbol %s used." % line[0])
            line = line[1:]
        elif len(line) > 0 and line[0] in '.':
            decoration = {
                '.': 'staccato',
                }[line[0]]
            line = line[1:]
        elif len(line) > 0 and line[0] in '!+':
            close_char = line[0]
            line = line[1:]

            decoration = ''
            while len(line) > 0 and line[0] != close_char:
                decoration += line[0]
                line = line[1:]

            if len(line) == 0:
                raise ParseError("Unterminated decoration %s" % decoration)
            assert line[0] == close_char
            line = line[1:]

        return decoration, line

    accidental_start_chars = '^_='
    def parse_accidental(self, line):
        accidental = ''
        while len(line) > 0 and line[0] in '^_=':
            accidental += line[0]
            line = line[1:]

        if accidental not in ('', '=', '^', '_'):
            raise ParseError("Unsupported accidental %s" % accidental)

        return accidental, line

    length_start_chars = '123456789/'
    def parse_length(self, line):
        lstr = ''

        numerator = ''
        denominator = ''
        slashes = 0
        while len(line) > 0 and line[0] in '0123456789':
            numerator += line[0]
            lstr += line[0]
            line = line[1:]
        while len(line) > 0 and line[0] == '/':
            slashes += 1
            lstr += line[0]
            line = line[1:]
        while len(line) > 0 and line[0] in '0123456789':
            denominator += line[0]
            lstr += line[0]
            line = line[1:]

        length = fractions.Fraction(1)
        if slashes > 0 and denominator == '':
            if numerator != '':
                length *= int(numerator)
            for _ in range(slashes):
                length /= 2
        elif numerator != '' and slashes == 0 and denominator == '':
            length *= int(numerator)
        elif slashes == 1 and denominator != '':
            length *= fractions.Fraction(
                int(numerator) if numerator != '' else 1,
                int(denominator))
        else:
            raise ParseError("Malformed note length %s" % lstr)

        return length, line

    note_start_chars = (decoration_start_chars
                        + accidental_start_chars
                        + 'abcdefgABCDEFGzxZx')
    def parse_note(self, line):
        ## Parse the ABC code.
        # http://abcnotation.com/wiki/abc:standard:v2.1#order_of_abc_constructs
        # <grace notes>
        # <chord symbols>
        # <annotations>/<decorations>
        # <accidentals>
        # <note>
        # <octave>
        # <note length>

        if len(line) > 0 and line[0] in self.decoration_start_chars:
            decoration, line = self.parse_decoration(line)
            logger.warning("Ignoring unsupported decoration %s", decoration)

        accidental = ''
        if len(line) > 0 and line[0] in self.accidental_start_chars:
            accidental, line = self.parse_accidental(line)

        if len(line) == 0:
            raise ParseError("Unexpected end of line")

        if line[0] in 'cdefgab':
            name = line[0].upper()
            octave = 5
        elif line[0] in 'CDEFGAB':
            name = line[0]
            octave = 4
        elif line[0] in 'zx':
            name = 'r'
            octave = 0
        else:
            raise ParseError("Unexpected character: %s" % line[0])
        line = line[1:]

        while len(line) > 0 and line[0] in ',\'':
            if line[0] == ',':
                octave -= 1
            elif line[0] == '\'':
                octave += 1
            line = line[1:]

        length = self.unit_length * self.next_length_multiplier

        if len(line) > 0 and line[0] in self.length_start_chars:
            length_multiplier, line = self.parse_length(line)
            length *= length_multiplier

        ## Build a note object.

        if name == 'r':
            pitch = music.Pitch('r')
        else:
            if accidental == '':
                accidental = self.key.accidental_map[name]
            elif accidental == '^':
                accidental = '#'
            elif accidental == '_':
                accidental = 'b'
            elif accidental == '=':
                accidental = ''
            else:
                raise AssertionError("Unexpected accidental %s" % accidental)

            pitch = music.Pitch(
                '%s%s%d' % (name, accidental, octave))

        if length.numerator == 1:
            base_duration = length
            dots = 0
        elif length.numerator == 3:
            base_duration = length * fractions.Fraction(2, 3)
            dots = 1
        else:
            raise ImporterError("Duration %s not supported." % length)

        assert base_duration.numerator == 1

        if base_duration.denominator > 32:
            logger.warning("Skipping short note %s.", length)
            return None, line

        if base_duration.denominator not in (1, 2, 4, 8, 16, 32):
            raise ImporterError("Duration %s not supported." % length)

        note = music.Note(
            pitches=[pitch],
            base_duration=audioproc.MusicalDuration(base_duration),
            dots=dots)

        return note, line

    grace_notes_start = '{'
    def parse_grace_notes(self, line):
        assert line[0] == '{'
        line = line[1:]
        notes = []
        while len(line) > 0 and line[0] != '}':
            if line[0] in self.note_start_chars:
                note, line = self.parse_note(line)
            else:
                raise ParseError("Unexpected character: %s" % line[0])
            if note is not None:
                notes.append(note)

        if len(line) == 0:
            raise ParseError("Unterminated grace notes")
        assert line[0] == '}'
        line = line[1:]

        return notes, line

    def parse_music(self, line):
        while len(line) > 0:
            if line[0] == '"':
                line = line[1:]
                while True:
                    if len(line) == 0:
                        raise ParseError("Unterminated string")
                    if line[0] == '"':
                        line = line[1:]
                        break
                    line = line[1:]
                continue

            if line[0] in self.note_start_chars:
                note, line = self.parse_note(line)
                if note is not None:
                    self.emit_note(note)
                self.next_length_multiplier = fractions.Fraction(1)
                continue

            if line[0] == '>' and len(self.notes) > 0:
                prev_note = self.notes[-1]
                while len(line) > 0 and line[0] == '>':
                    prev_note.base_duration = audioproc.MusicalDuration(
                        prev_note.base_duration * fractions.Fraction(3, 2))
                    self.next_length_multiplier /= 2
                    line = line[1:]
                continue

            if line[0] == '<' and len(self.notes) > 0:
                prev_note = self.notes[-1]
                while len(line) > 0 and line[0] == '<':
                    prev_note.base_duration = audioproc.MusicalDuration(
                        prev_note.base_duration * fractions.Fraction(1, 2))
                    self.next_length_multiplier *= fractions.Fraction(3, 2)
                    line = line[1:]
                continue

            if line[0] in self.grace_notes_start:
                grace_notes, line = self.parse_grace_notes(line)
                logger.warning("Ignoring grace notes %s", ''.join(str(n) for n in grace_notes))
                continue

            if line[0] == '|':
                self.emit_measure()
                line = line[1:]
                if len(line) > 0 and line[0] == ']':
                    line = line[1:]
                continue

            if line[0] == '(':
                line = line[1:]
                # TODO: support slur start.
                continue

            if line[0] == ')':
                line = line[1:]
                # TODO: support slur end.
                continue

            if line[0] == '-':
                line = line[1:]
                # TODO: support ties.
                continue

            if line[0] == ' ':
                line = line[1:]
                continue

            if line[0] == '[' and len(line) >= 4 and line[1] in 'IKLMmNPQRrUV' and line[2] == ':':
                line = line[1:]
                field = line[0]
                line = line[1:]
                line = line[1:]  # skip colon
                contents = ''
                while True:
                    if len(line) == 0:
                        raise ParseError("Unterminated inline field")
                    if line[0] == ']':
                        line = line[1:]
                        break
                    contents += line[0]
                    line = line[1:]
                self.parse_information_field(field, contents)
                continue

            logger.warning("Ignoring unsupported character: %s", line[0])
            line = line[1:]
