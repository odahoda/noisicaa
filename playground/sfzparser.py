#!/usr/bin/python

import enum
import os
import os.path
import pprint
import re
import subprocess
import sys
import textwrap
import unittest
import wave

import numpy
import lilv
from pyparsing import Word, Literal, ZeroOrMore, alphas, alphanums, stringEnd, restOfLine, ParseBaseException, ParseException, QuotedString, FollowedBy, lineEnd, Regex, locatedExpr


class IncludeException(ParseBaseException):
    pass

class UnknownOpCodeException(ParseBaseException):
    pass

class InvalidValueException(ParseBaseException):
    pass

class InvalidSectionException(ParseBaseException):
    pass

class SampleMissingException(ParseBaseException):
    pass


class OpCodeType(enum.Enum):
    INT = 'int'
    FLOAT = 'float'
    PATH = 'path'
    PITCH = 'pitch'
    STRING = 'string'


pitch2midi = {}
k = 0
for o in range(10):
    for n in [('C',),
              ('C#', 'Db'),
              ('D',),
              ('D#', 'Eb'),
              ('E',),
              ('F',),
              ('F#', 'Gb'),
              ('G',),
              ('G#', 'Ab'),
              ('A',),
              ('A#', 'Bb'),
              ('B',)]:
        if k < 128:
            for p in n:
                pitch2midi['%s%d' % (p, o)] = k
        k += 1


def expand_name(name):
    result = set()
    if 'CC' in name:
        for cc in range(0, 128):
            result |= expand_name(name.replace('CC', str(cc)))

    elif 'EQ' in name:
        for eq in range(1, 4):
            result |= expand_name(name.replace('EQ', str(eq)))

    elif 'VEL' in name:
        for vel in range(1, 128):
            result |= expand_name(name.replace('VEL', str(vel)))

    else:
        result.add(name)

    return result


def normalize_path(path):
    return path.replace('\\', '/')


class OpCode(object):
    def __init__(self, name, type, range=None):
        self.name = name
        self.type = type
        self.range = range

        self.valid_names = expand_name(self.name)

    def parse_value(self, s):
        if self.type == OpCodeType.INT:
            return int(s)
        if self.type == OpCodeType.FLOAT:
            return float(s)
        if self.type == OpCodeType.PATH:
            return normalize_path(s)
        if self.type == OpCodeType.STRING:
            return s
        if self.type == OpCodeType.PITCH:
            if re.match(r'-?[0-9]+', s):
                return int(s)
            else:
                try:
                    return pitch2midi[s.upper()]
                except KeyError:
                    raise ValueError("Invalid pitch '%s'" % s)

        assert False, self.type

opcodes = [
    # Sample definition
    OpCode('sample', OpCodeType.PATH),
    OpCode('default_path', OpCodeType.PATH),

    # Input controls
    OpCode('lochan', OpCodeType.INT),
    OpCode('hichan', OpCodeType.INT),
    OpCode('lokey', OpCodeType.PITCH),
    OpCode('hikey', OpCodeType.PITCH),
    OpCode('key', OpCodeType.PITCH),
    OpCode('lovel', OpCodeType.INT),
    OpCode('hivel', OpCodeType.INT),
    OpCode('loccCC', OpCodeType.INT),
    OpCode('hiccCC', OpCodeType.INT),
    OpCode('lobend', OpCodeType.INT),
    OpCode('hibend', OpCodeType.INT),
    OpCode('lochanaft', OpCodeType.INT),
    OpCode('hichanaft', OpCodeType.INT),
    OpCode('lopolyaft', OpCodeType.INT),
    OpCode('hipolyaft', OpCodeType.INT),
    OpCode('lorand', OpCodeType.FLOAT),
    OpCode('hirand', OpCodeType.FLOAT),
    OpCode('lobpm', OpCodeType.FLOAT),
    OpCode('hibpm', OpCodeType.FLOAT),
    OpCode('seq_length', OpCodeType.INT),
    OpCode('seq_position', OpCodeType.INT),
    OpCode('sw_lokey', OpCodeType.PITCH),
    OpCode('sw_hikey', OpCodeType.PITCH),
    OpCode('sw_last', OpCodeType.PITCH),
    OpCode('sw_down', OpCodeType.PITCH),
    OpCode('sw_up', OpCodeType.PITCH),
    OpCode('sw_previous', OpCodeType.PITCH),
    OpCode('sw_vel', OpCodeType.STRING, ['current', 'previous']),
    OpCode('trigger', OpCodeType.STRING, ['attack', 'release', 'first', 'legato']),
    OpCode('group', OpCodeType.INT),
    OpCode('off_by', OpCodeType.INT),
    OpCode('off_mode', OpCodeType.STRING, ['fast', 'normal']),
    OpCode('on_loccCC', OpCodeType.INT),
    OpCode('on_hiccCC', OpCodeType.INT),

    # Performance parameters
    OpCode('delay', OpCodeType.FLOAT),
    OpCode('delay_random', OpCodeType.FLOAT),
    OpCode('delay_ccCC', OpCodeType.FLOAT),
    OpCode('offset', OpCodeType.INT),
    OpCode('offset_random', OpCodeType.INT),
    OpCode('offset_ccCC', OpCodeType.INT),
    OpCode('end', OpCodeType.INT),
    OpCode('count', OpCodeType.INT),
    OpCode('loop_mode', OpCodeType.STRING, ['no_loop', 'loop_continuous']),
    OpCode('loop_start', OpCodeType.INT),
    OpCode('loop_end', OpCodeType.INT),
    OpCode('sync_beats', OpCodeType.FLOAT),
    OpCode('sync_offset', OpCodeType.FLOAT),

    # Pitch
    OpCode('transpose', OpCodeType.INT),
    OpCode('tune', OpCodeType.INT),
    OpCode('pitch_keycenter', OpCodeType.PITCH),
    OpCode('pitch_keytrack', OpCodeType.INT),
    OpCode('pitch_veltrack', OpCodeType.INT),
    OpCode('pitch_random', OpCodeType.INT),
    OpCode('bend_up', OpCodeType.INT),
    OpCode('bend_down', OpCodeType.INT),
    OpCode('bend_step', OpCodeType.INT),

    # Pitch EG
    OpCode('pitcheg_delay', OpCodeType.FLOAT),
    OpCode('pitcheg_start', OpCodeType.FLOAT),
    OpCode('pitcheg_attack', OpCodeType.FLOAT),
    OpCode('pitcheg_hold', OpCodeType.FLOAT),
    OpCode('pitcheg_decay', OpCodeType.FLOAT),
    OpCode('pitcheg_sustain', OpCodeType.FLOAT),
    OpCode('pitcheg_release', OpCodeType.FLOAT),
    OpCode('pitcheg_depth', OpCodeType.INT),
    OpCode('pitcheg_vel2delay', OpCodeType.FLOAT),
    OpCode('pitcheg_vel2attack', OpCodeType.FLOAT),
    OpCode('pitcheg_vel2hold', OpCodeType.FLOAT),
    OpCode('pitcheg_vel2decay', OpCodeType.FLOAT),
    OpCode('pitcheg_vel2sustain', OpCodeType.FLOAT),
    OpCode('pitcheg_vel2release', OpCodeType.FLOAT),
    OpCode('pitcheg_vel2depth', OpCodeType.INT),

    # Pitch LFO
    OpCode('pitchlfo_delay', OpCodeType.FLOAT),
    OpCode('pitchlfo_fade', OpCodeType.FLOAT),
    OpCode('pitchlfo_freq', OpCodeType.FLOAT),
    OpCode('pitchlfo_depth', OpCodeType.INT),
    OpCode('pitchlfo_depthccCC', OpCodeType.INT),
    OpCode('pitchlfo_depthchanaft', OpCodeType.INT),
    OpCode('pitchlfo_depthpolyaft', OpCodeType.INT),
    OpCode('pitchlfo_freqccN', OpCodeType.FLOAT),
    OpCode('pitchlfo_freqchanaft', OpCodeType.FLOAT),
    OpCode('pitchlfo_freqpolyaft', OpCodeType.FLOAT),

    # Filter
    OpCode('fil_type', OpCodeType.STRING, ['lpf_1p', 'hpf_1p', 'lpf_2p', 'hpf_2p', 'bpf_2p', 'brf_2p']),
    OpCode('cutoff', OpCodeType.FLOAT),
    OpCode('cutoff_ccCC', OpCodeType.INT),
    OpCode('cutoff_chanaft', OpCodeType.INT),
    OpCode('cutoff_polyaft', OpCodeType.INT),
    OpCode('resonance', OpCodeType.FLOAT),
    OpCode('fil_keytrack', OpCodeType.INT),
    OpCode('fil_keycenter', OpCodeType.INT),
    OpCode('fil_veltrack', OpCodeType.INT),
    OpCode('fil_random', OpCodeType.INT),

    # Filter EG
    OpCode('fileg_delay', OpCodeType.FLOAT),
    OpCode('fileg_start', OpCodeType.FLOAT),
    OpCode('fileg_attack', OpCodeType.FLOAT),
    OpCode('fileg_hold', OpCodeType.FLOAT),
    OpCode('fileg_decay', OpCodeType.FLOAT),
    OpCode('fileg_sustain', OpCodeType.FLOAT),
    OpCode('fileg_release', OpCodeType.FLOAT),
    OpCode('fileg_depth', OpCodeType.INT),
    OpCode('fileg_vel2delay', OpCodeType.FLOAT),
    OpCode('fileg_vel2attack', OpCodeType.FLOAT),
    OpCode('fileg_vel2hold', OpCodeType.FLOAT),
    OpCode('fileg_vel2decay', OpCodeType.FLOAT),
    OpCode('fileg_vel2sustain', OpCodeType.FLOAT),
    OpCode('fileg_vel2release', OpCodeType.FLOAT),
    OpCode('fileg_vel2depth', OpCodeType.INT),

    # Filter LFO
    OpCode('fillfo_delay', OpCodeType.FLOAT),
    OpCode('fillfo_fade', OpCodeType.FLOAT),
    OpCode('fillfo_freq', OpCodeType.FLOAT),
    OpCode('fillfo_depth', OpCodeType.INT),
    OpCode('fillfo_depthccCC', OpCodeType.INT),
    OpCode('fillfo_depthchanaft', OpCodeType.INT),
    OpCode('fillfo_depthpolyaft', OpCodeType.INT),
    OpCode('fillfo_freqccN', OpCodeType.FLOAT),
    OpCode('fillfo_freqchanaft', OpCodeType.FLOAT),
    OpCode('fillfo_freqpolyaft', OpCodeType.FLOAT),

    # Amplifier
    OpCode('volume', OpCodeType.FLOAT),
    OpCode('pan', OpCodeType.FLOAT),
    OpCode('width', OpCodeType.FLOAT),
    OpCode('position', OpCodeType.FLOAT),
    OpCode('amp_keytrack', OpCodeType.FLOAT),
    OpCode('amp_keycenter', OpCodeType.INT),
    OpCode('amp_veltrack', OpCodeType.FLOAT),
    OpCode('amp_velcurve_VEL', OpCodeType.FLOAT),
    OpCode('amp_random', OpCodeType.FLOAT),
    OpCode('rt_decay', OpCodeType.FLOAT),
    OpCode('output', OpCodeType.INT),
    OpCode('gain_ccN', OpCodeType.FLOAT),
    OpCode('xfin_lokey', OpCodeType.PITCH),
    OpCode('xfin_hikey', OpCodeType.PITCH),
    OpCode('xfout_lokey', OpCodeType.PITCH),
    OpCode('xfout_hikey', OpCodeType.PITCH),
    OpCode('xf_keycurve', OpCodeType.STRING, ['gain', 'power']),
    OpCode('xfin_lovel', OpCodeType.INT),
    OpCode('xfin_hivel', OpCodeType.INT),
    OpCode('xfout_lovel', OpCodeType.INT),
    OpCode('xfout_hivel', OpCodeType.INT),
    OpCode('xf_velcurve', OpCodeType.STRING, ['gain', 'power']),
    OpCode('xfin_loccCC', OpCodeType.INT),
    OpCode('xfin_hiccCC', OpCodeType.INT),
    OpCode('xfout_loccCC', OpCodeType.INT),
    OpCode('xfout_hiccCC', OpCodeType.INT),
    OpCode('cf_cccurve', OpCodeType.STRING, ['gain', 'power']),

    # Amplifier EG
    OpCode('ampeg_delay', OpCodeType.FLOAT),
    OpCode('ampeg_start', OpCodeType.FLOAT),
    OpCode('ampeg_attack', OpCodeType.FLOAT),
    OpCode('ampeg_hold', OpCodeType.FLOAT),
    OpCode('ampeg_decay', OpCodeType.FLOAT),
    OpCode('ampeg_sustain', OpCodeType.FLOAT),
    OpCode('ampeg_release', OpCodeType.FLOAT),
    OpCode('ampeg_vel2delay', OpCodeType.FLOAT),
    OpCode('ampeg_vel2attack', OpCodeType.FLOAT),
    OpCode('ampeg_vel2hold', OpCodeType.FLOAT),
    OpCode('ampeg_vel2decay', OpCodeType.FLOAT),
    OpCode('ampeg_vel2sustain', OpCodeType.FLOAT),
    OpCode('ampeg_vel2release', OpCodeType.FLOAT),
    OpCode('ampeg_delayccCC', OpCodeType.FLOAT),
    OpCode('ampeg_startccCC', OpCodeType.FLOAT),
    OpCode('ampeg_attackccCC', OpCodeType.FLOAT),
    OpCode('ampeg_holdccCC', OpCodeType.FLOAT),
    OpCode('ampeg_decayccCC', OpCodeType.FLOAT),
    OpCode('ampeg_sustainccCC', OpCodeType.FLOAT),
    OpCode('ampeg_releaseccCC', OpCodeType.FLOAT),

    # Amplifier LFO
    OpCode('amplfo_delay', OpCodeType.FLOAT),
    OpCode('amplfo_fade', OpCodeType.FLOAT),
    OpCode('amplfo_freq', OpCodeType.FLOAT),
    OpCode('amplfo_depth', OpCodeType.INT),
    OpCode('amplfo_depthccCC', OpCodeType.INT),
    OpCode('amplfo_depthchanaft', OpCodeType.INT),
    OpCode('amplfo_depthpolyaft', OpCodeType.INT),
    OpCode('amplfo_freqccN', OpCodeType.FLOAT),
    OpCode('amplfo_freqchanaft', OpCodeType.FLOAT),
    OpCode('amplfo_freqpolyaft', OpCodeType.FLOAT),

    # Equaliyer
    OpCode('eqEQ_freq', OpCodeType.FLOAT),
    OpCode('eqEQ_freqccCC', OpCodeType.FLOAT),
    OpCode('eqEQ_vel2freq', OpCodeType.FLOAT),
    OpCode('eqEQ_bw', OpCodeType.FLOAT),
    OpCode('eqEQ_bwccCC', OpCodeType.FLOAT),
    OpCode('eqEQ_gain', OpCodeType.FLOAT),
    OpCode('eqEQ_gainccCC', OpCodeType.FLOAT),
    OpCode('eqEQ_vel2gain', OpCodeType.FLOAT),

    # Effects
    OpCode('effect1', OpCodeType.FLOAT),
    OpCode('effect2', OpCodeType.FLOAT),
    ]

opmap = {}
for op in opcodes:
    for n in op.valid_names:
        opmap[n] = op


class Instrument(object):
    def __init__(self, path):
        self.path = path
        self.control = None
        self.regions = []

    def __repr__(self):
        return '<instrument "%s">' % self.path + ''.join('\n  %r' % s for s in self.regions)

    def to_csnd(self):
        sample_map = {}
        fnum = 1
        for region in self.regions:
            if region.sample in sample_map:
                continue
            sample_map[region.sample] = fnum
            fnum += 1

        csnd_prog = textwrap.dedent("""\
        <CsoundSynthesizer>
        <CsOptions>
        -odac
        </CsOptions>
        <CsInstruments>
        ; Auto generated from %(path)s

        sr = 44100
        ksmps = 32
        nchnls = 2
        0dbfs  = 1

        massign	0, 1

        instr 1
        iNote = notnum()
        iVel = veloc()

        ; 0: attack
        ; 1: sustain
        ; 2: release
        kState init 0

        if release() == 1 then
            kState = 2
        endif

        """ % {'path': self.path})

        for rnum, region in enumerate(self.regions):
            conditions = []
            if region.get('lokey', None) is not None:
                conditions.append('iNote >= %d' % region['lokey'])
            if region.get('hikey', None) is not None:
                conditions.append('iNote <= %d' % region['hikey'])

            if conditions:
                csnd_prog += 'if (%s) then\n' % ' && '.join(conditions)

            csnd_prog += 'instrnum%d = %d + iNote / 1000\n' % (rnum, 10 + rnum)

            trigger = region.get('trigger', 'attack')
            if trigger == 'attack':
                csnd_prog += 'if kState == 0 then\n'
                csnd_prog += 'event "i", instrnum%d, 0, -1, iNote, iVel\n' % rnum
                csnd_prog += 'endif\n'
                csnd_prog += 'if kState == 2 then\n'
                csnd_prog += 'event "i", -instrnum%d, 0, 1\n' % rnum
                csnd_prog += 'endif\n'
            elif trigger == 'release':
                csnd_prog += 'if kState == 2 then\n'
                csnd_prog += 'event "i", instrnum%d, 0, -1, iNote, iVel\n' % rnum
                csnd_prog += 'endif\n'
            else:
                raise RuntimeError(trigger)

            if conditions:
                csnd_prog += 'endif\n'

        csnd_prog += textwrap.dedent("""\

        if kState == 0 then
            kState = 1
        endif

        endin
        """)

        for rnum, region in enumerate(self.regions):
            fnum = sample_map[region.sample]

            csnd_prog += "; === region %d =============================================\n" % rnum
            csnd_prog += "; %r\n" % region
            csnd_prog += "instr %d, region%d\n" % (10 + rnum, rnum)

            csnd_prog += 'iNote = p4\n'
            csnd_prog += 'iVel = p5\n'
            csnd_prog += 'iVolume = -20 * log10(127^2 / iVel^2)\n'

            csnd_prog += 'print iNote, iVel, iVolume\n'

            csnd_prog += 'ichannels = ftchnls(%d)\n' % fnum

            loop_mode = region.get('loop_mode', None)
            if loop_mode == 'one_shot':
                loop_mode = 0
            elif loop_mode == 'no_loop':
                loop_mode = 0
            else:
                loop_mode = -1

            csnd_prog += textwrap.dedent("""\
        if (ichannels == 1) then
            aregl loscil 1, cpsmidinn(iNote), %(fnum)d, cpsmidinn(%(keycenter)d), %(loop)d
            aregr = aregl
        elseif (ichannels == 2) then
            aregl, aregr loscil 1, cpsmidinn(iNote), %(fnum)d, cpsmidinn(%(keycenter)d), %(loop)d
        else
            aregl = 0
            aregr = 0
        endif

        """ % {'fnum': fnum,
               'keycenter': region.get('pitch_keycenter', 60),
               'loop': loop_mode})

            if region.get('volume', None) is not None:
                csnd_prog += 'aregl = db(%f) * aregl\n' % region['volume']
                csnd_prog += 'aregr = db(%f) * aregr\n' % region['volume']

            csnd_prog += 'aregl = db(iVolume) * aregl\n'
            csnd_prog += 'aregr = db(iVolume) * aregr\n'

            segments = []
            attack = region.get('ampeg_attack', 0.0)
            decay = region.get('ampeg_decay', 0.0)
            sustain = region.get('ampeg_sustain', 0.0)
            release = region.get('ampeg_release', 0.0)
            if attack > 0.0:
                segments += [0.0, attack]
            segments += [1.0]
            if decay > 0.0:
                segments += [decay, sustain]
            if release > 0.0:
                segments += [release, 0.0]

            if len(segments) > 1:
                csnd_prog += 'aamp %s %s\n' % (
                    'linsegr' if release > 0 else 'linseg',
                    ', '.join('%f' % s for s in segments))
                csnd_prog += 'aregl = aamp * aregl\n'
                csnd_prog += 'aregr = aamp * aregr\n'

            csnd_prog += '    outs aregl, aregr\n'

            csnd_prog += "endin\n"
            csnd_prog += "\n\n"

        csnd_prog += textwrap.dedent("""\
        </CsInstruments>
        <CsScore>
        ;f0 3600

        """)

        for sample, fnum in sorted(sample_map.items(), key=lambda a: a[1]):
            csnd_prog += textwrap.dedent("""\
                f %d 0 0 1 "%s" 0 0 0
            """ % (fnum, sample))


        csnd_prog += textwrap.dedent("""\

        e 3600
        </CsScore>
        </CsoundSynthesizer>
        """)

        return csnd_prog


class Section(object):
    def __init__(self, instr, name, group=None, control=None):
        self._instr = instr
        self._name = name
        self._group = group
        self._control = control
        self._opcodes = {}
        self._opcode_locs = {}

    def __repr__(self):
        r = '<%s>' % self._name
        if self._control is not None:
            r += ''.join(' %s=%r' % (n, v)
                          for n, v in sorted(self._control._opcodes.items()))
        if self._group is not None:
            r += ''.join(' %s=%r' % (n, v)
                          for n, v in sorted(self._group._opcodes.items()))
        r += ''.join(' %s=%r' % (n, v)
                      for n, v in sorted(self._opcodes.items()))

        return r

    def __getitem__(self, name):
        try:
            return self._opcodes[name]
        except KeyError:
            if self._group is not None:
                return self._group[name]
            raise KeyError

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def get_opcode_loc(self, name):
        try:
            return self._opcode_locs[name]
        except KeyError:
            if self._group is not None:
                return self._group._opcode_locs[name]
            raise AttributeError

class Region(Section):
    @property
    def sample(self):
        base = os.path.dirname(self._instr.path)
        if self._control is not None:
            default_path = self._control.get('default_path', None)
            if default_path:
                base = os.path.join(base, default_path)
        return os.path.join(base, self['sample'])


class ParserState(object):
    def __init__(self):
        self.current_group = None
        self.current_control = None
        self.current_section = None


class SFZParser(object):
    def __init__(self, path, text, state=None):
        self.path = path
        self.base_path = os.path.dirname(path)
        self.text = text
        self.state = state

        opcode_name = Word(alphanums + '_')
        value = Regex(r'.*?(?=\s*(([a-zA-Z0-9_]+=)|//|<[a-z]|$))', re.MULTILINE)
        opcode = locatedExpr(opcode_name) + Literal('=').suppress() + value
        opcode.setParseAction(self.handle_opcode)

        section_name = Literal('<').suppress() + Word(alphas) + Literal('>').suppress()
        section = section_name
        section.setParseAction(self.handle_section)

        include = Literal('#include').suppress() + locatedExpr(QuotedString('"'))
        include.setParseAction(self.handle_include)

        statement = (section
                     ^ opcode
                     ^ include)

        self.sfz_file = ZeroOrMore(statement) + stringEnd

        comment = Literal('//') + restOfLine
        self.sfz_file.ignore(comment)

    def handle_include(self, s, loc, toks):
        path = os.path.join(self.base_path, normalize_path(toks[0].value))
        try:
            with open(path) as fp:
                f = fp.read()
        except IOError as exc:
            raise IncludeException(
                s, loc=toks[0].locn_start, msg=str(exc))
        subparser = SFZParser(path, f, self.state)
        subparser.sfz_file.parseString(f)

    def handle_section(self, s, loc, toks):
        name = toks[0]
        if name == 'region':
            section = Region(self.state.instr, name, group=self.state.current_group, control=self.state.current_control)
            self.state.instr.regions.append(section)
        elif name == 'group':
            section = Section(self.state.instr, name)
            self.state.current_group = section
        elif name == 'control':
            section = Section(self.state.instr, name)
            self.state.current_control = section
        else:
            raise InvalidSectionException(
                s, loc, "Invalid section name '%s'" % name)

        self.state.current_section = section

    def handle_opcode(self, s, loc, toks):
        loc = toks[0].locn_start
        name = toks[0].value

        try:
            opdef = opmap[name]
        except KeyError:
            raise UnknownOpCodeException(
                s, loc=loc, msg="Unknown opcode '%s'" % key)

        try:
            value = opdef.parse_value(toks[1])
        except ValueError as exc:
            raise InvalidValueException(
                s, loc=loc,
                msg="Invalid value for opcode '%s': %s" % (key, str(exc)))

        self.state.current_section._opcodes[name] = value
        self.state.current_section._opcode_locs[name] = (s, loc)

    def parse(self):
        self.state = ParserState()
        self.state.instr = Instrument(os.path.abspath(self.path))
        self.sfz_file.parseString(self.text)
        for region in self.state.instr.regions:
            if not os.path.isfile(region.sample):
                s, loc = region.get_opcode_loc('sample')
                raise SampleMissingException(
                    s, loc, "Missing sample '%s'" % region.sample)
        return self.state.instr


class TestParseInstrument(unittest.TestCase):
    INSTR_ROOT = '/storage/home/share/instruments/'

    def test_foo(self):
        for dirpath, dirnames, filenames in os.walk(self.INSTR_ROOT):
            for filename in filenames:
                if not filename.lower().endswith('.sfz'):
                    continue
                path = os.path.join(dirpath, filename)
                with self.subTest(path=path):
                    with open(path) as fp:
                        contents = fp.read()
                    parser = SFZParser(path, contents)
                    instr = parser.parse()
                    csnd = instr.to_csnd()


# class TestLinuxSampler(unittest.TestCase):
#     def test_foo(self):
#         # ADD CHANNEL
#         # LOAD ENGINE SFZ 0
#         # CREATE AUDIO_OUTPUT_DEVICE JACK
#         # SET CHANNEL AUDIO_OUTPUT_DEVICE 0 0
#         # LOAD INSTRUMENT "$(path)s" 0 0
#         # SEND CHANNEL MIDI_DATA NOTE_ON 0 56 112

#         world = lilv.World()
#         world.load_all()

#         nframes = 1024

#         URI = 'http://calf.sourceforge.net/plugins/Fluidsynth'
#         URI = 'http://kxstudio.sf.net/carla/plugins/zynaddsubfx'
#         URI = 'http://linuxsampler.org/plugins/linuxsampler'
#         plugin = world.get_all_plugins().get_by_uri(
#             world.new_uri(URI))
#         self.assertTrue(plugin is not None)

#         lv2_OutputPort  = world.new_uri(lilv.LILV_URI_OUTPUT_PORT)
#         lv2_InputPort  = world.new_uri(lilv.LILV_URI_INPUT_PORT)
#         lv2_AudioPort   = world.new_uri(lilv.LILV_URI_AUDIO_PORT)
#         lv2_ControlPort   = world.new_uri(lilv.LILV_URI_CONTROL_PORT)
#         lv2_EventPort   = world.new_uri(lilv.LILV_URI_EVENT_PORT)
#         lv2_AtomPort   = world.new_uri(lilv.LILV_URI_ATOM_PORT)
#         lv2_CvPort   = world.new_uri(lilv.LILV_URI_CV_PORT)
#         n_audio_out = plugin.get_num_ports_of_class(lv2_OutputPort, lv2_AudioPort)
#         self.assertEqual(n_audio_out, 2)

#         buffers = {}
#         for index in range(plugin.get_num_ports()):
#             port = plugin.get_port_by_index(index)
#             print("port %d" % index)
#             print("is_a(OUTPUT_PORT) = %s" % port.is_a(lv2_OutputPort))
#             print("is_a(INPUT_PORT) = %s" % port.is_a(lv2_InputPort))
#             print("is_a(AUDIO_PORT) = %s" % port.is_a(lv2_AudioPort))
#             print("is_a(CONTROL_PORT) = %s" % port.is_a(lv2_ControlPort))
#             print("is_a(EVENT_PORT) = %s" % port.is_a(lv2_EventPort))
#             print("is_a(ATOM_PORT) = %s" % port.is_a(lv2_AtomPort))
#             print("is_a(CV_PORT) = %s" % port.is_a(lv2_CvPort))
#             if port.is_a(lv2_AudioPort):
#                 buffers[index] = numpy.ndarray([nframes], numpy.float32)

#             elif port.is_a(lv2_ControlPort):
#                 buffers[index] = numpy.ndarray([1], numpy.float32)

#             elif port.is_a(lv2_AtomPort):
#                 buffers[index] = numpy.ndarray([1000], numpy.float32)

#             else:
#                 raise ValueError("Unhandled port type")

#         wav_out = wave.open('/tmp/foo.wav', 'w')
#         wav_out.setnchannels(2)
#         wav_out.setsampwidth(2)
#         wav_out.setframerate(44100)

#         # SIGSEGVs. Linuxsampler needs the http://lv2plug.in/ns/ext/urid#map
#         # feature, or http://svn.linuxsampler.org/cgi-bin/viewvc.cgi/linuxsampler/trunk/src/hostplugins/lv2/PluginLv2.cpp?revision=2837&view=markup&sortby=file#l64 crashes.
#         # The swig'd lilv doesn't support features.
#         instance = lilv.Instance(plugin, 44100)
#         help(instance)
#         print(1)
#         for index in range(plugin.get_num_ports()):
#             port = plugin.get_port_by_index(index)
#             if index in buffers:
#                 instance.connect_port(index, buffers[index])

#         for i in range(100):
#             print(i)
#             instance.run(nframes)


if len(sys.argv) == 1:
    sys.exit(unittest.main(verbosity=2))

else:
    with open(sys.argv[1]) as fp:
        f = fp.read()

        parser = SFZParser(sys.argv[1], f)
        try:
            instr = parser.parse()
        except ParseBaseException as exc:
            print(sys.argv[1])
            print(exc)
            for n, l in enumerate(f.splitlines(False), 1):
                if n == exc.lineno:
                    print('*% 3d  %s' % (n, l))
                    print(' ' * (exc.col + 5) + '^')
                elif exc.lineno - 2 <= n <= exc.lineno + 2:
                    print(' % 3d  %s' % (n, l))
                    sys.exit(1)


    csnd_prog = instr.to_csnd()
    print(csnd_prog)
    with open('/tmp/foo.csnd', 'w') as fp:
        fp.write(csnd_prog)

    argv = ['csound', '-d', '-odac', '-m0']
    if len(sys.argv) >= 3:
        argv += ['-F', sys.argv[2]]
    else:
        argv += ['-Ma']
    argv += ['/tmp/foo.csnd']
    subprocess.run(argv)


