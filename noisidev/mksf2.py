#!/usr/bin/env python3

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

import argparse
import contextlib
import os
import os.path
import sys
import struct
import wave

import yaml


class RiffWriter(object):
    def __init__(self, fp, identifier):
        if isinstance(identifier, str):
            identifier = identifier.encode('ascii')

        if len(identifier) != 4:
            raise ValueError("Invalid list identifier '%s'", identifier)

        self.__fp = fp

        self.__stack = []

        self.__chunk_size_pos = None

        self.start_chunk(b'RIFF')
        self.__fp.write(identifier)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()
        return False

    def close(self):
        self.end_chunk()

    def __push(self):
        self.__stack.append(self.__chunk_size_pos)

    def __pop(self):
        self.__chunk_size_pos = self.__stack.pop(-1)

    def start_list(self, identifier):
        if isinstance(identifier, str):
            identifier = identifier.encode('ascii')

        if len(identifier) != 4:
            raise ValueError("Invalid list identifier '%s'", identifier)

        self.start_chunk(b'LIST')
        self.__fp.write(identifier)

    def end_list(self):
        self.end_chunk()

    @contextlib.contextmanager
    def list(self, identifier):
        self.start_list(identifier)
        yield
        self.end_list()

    def start_chunk(self, identifier):
        if isinstance(identifier, str):
            identifier = identifier.encode('ascii')

        if len(identifier) != 4:
            raise ValueError("Invalid identifier '%s'", identifier)

        self.__push()

        self.__fp.write(identifier)
        self.__chunk_size_pos = self.__fp.tell()
        self.__fp.write(struct.pack('<i', 0))

    def end_chunk(self):
        bytes_written = self.__fp.tell() - self.__chunk_size_pos - 4
        if bytes_written % 2 == 1:
            self.__fp.write(b'\0')
        self.__fp.seek(self.__chunk_size_pos, os.SEEK_SET)
        self.__fp.write(struct.pack('<i', bytes_written))
        self.__fp.seek(0, os.SEEK_END)

        self.__pop()

    @contextlib.contextmanager
    def chunk(self, identifier):
        self.start_chunk(identifier)
        yield
        self.end_chunk()

    def write(self, data):
        if not isinstance(data, bytes):
            raise TypeError("Expected bytes, got %s" % type(data).__name__)

        self.__fp.write(data)


class Struct(object):
    FIELDSPEC = None

    def __init__(self, **kwargs):
        self.__spec = '<' + ''.join(s for s, _ in self.FIELDSPEC)

        for _, n in self.FIELDSPEC:
            setattr(self, n, kwargs.get(n))

    def pack(self):
        fields = []
        for _, n in self.FIELDSPEC:
            fields.append(getattr(self, n))
        return struct.pack(self.__spec, *fields)


class sfPresetHeader(Struct):
    FIELDSPEC = [
        ('20s', 'achPresetName'),
        ('H', 'wPreset'),
        ('H', 'wBank'),
        ('H', 'wPresetBagNdx'),
        ('I', 'dwLibrary'),
        ('I', 'dwGenre'),
        ('I', 'dwMorphology'),
    ]


class sfPresetBag(Struct):
    FIELDSPEC = [
        ('H', 'wGenNdx'),
        ('H', 'wModNdx'),
    ]


class sfModList(Struct):
    FIELDSPEC = [
        ('H', 'sfModSrcOper'),
        ('H', 'sfModDestOper'),
        ('h', 'modAmount'),
        ('H', 'sfModAmtSrcOper'),
        ('H', 'sfModTransOper'),
    ]


class sfGenList(Struct):
    FIELDSPEC = [
        ('H', 'sfGenOper'),
        ('h', 'genAmount'),
    ]


class sfInst(Struct):
    FIELDSPEC = [
        ('20s', 'achInstName'),
        ('H', 'wInstBagNdx'),
    ]


class sfInstBag(Struct):
    FIELDSPEC = [
        ('H', 'wInstGenNdx'),
        ('H', 'wInstModNdx'),
    ]


class sfInstGenList(Struct):
    FIELDSPEC = [
        ('H', 'sfGenOper'),
        ('h', 'genAmount'),
    ]


class sfSample(Struct):
    FIELDSPEC = [
        ('20s', 'achSampleName'),
        ('i', 'dwStart'),
        ('i', 'dwEnd'),
        ('i', 'dwStartloop'),
        ('i', 'dwEndloop'),
        ('i', 'dwSampleRate'),
        ('B', 'byOriginalPitch'),
        ('b', 'chPitchCorrection'),
        ('h', 'wSampleLink'),
        ('H', 'sfSampleType'),
    ]


def main(argv):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('input', type=str)
    argparser.add_argument('--output', '-o', type=str, required=True)
    argparser.add_argument('--search_paths', type=str, default=None)
    args = argparser.parse_args(argv[1:])

    if args.search_paths is not None:
        search_paths = args.search_paths.split(':')
    else:
        search_paths = [os.path.dirname(args.input)]

    with open(args.input, 'r') as fp:
        definition = yaml.load(fp)

    with open(args.output, 'wb') as fp:
        with RiffWriter(fp, 'sfbk') as writer:
            with writer.list('INFO'):
                with writer.chunk('ifil'):
                    writer.write(struct.pack('<hh', 2, 1))

                with writer.chunk('isng'):
                    writer.write(definition.get('sound-engine', 'EMU8000').encode('ascii'))
                    writer.write(b'\0')

                with writer.chunk('INAM'):
                    writer.write(definition['name'].encode('ascii'))
                    writer.write(b'\0')

            sample_offset = 0

            phdr = []
            pbag = []
            pmod = []
            pgen = []
            inst = []
            ibag = []
            imod = []
            igen = []
            shdr = []

            with writer.list('sdta'):
                with writer.chunk('smpl'):
                    for instr in definition['instruments']:
                        for sp in search_paths:
                            path = os.path.join(sp, instr['file'])
                            if os.path.isfile(path):
                                break
                        else:
                            raise FileNotFoundError(instr['file'])

                        with wave.open(path, 'rb') as wfp:
                            if wfp.getnchannels() != 1:
                                raise RuntimeError("Only mono samples are supported.")
                            if wfp.getsampwidth() != 2:
                                raise RuntimeError("Only 16 bit samples are supported.")

                            num_frames = wfp.getnframes()

                            phdr.append(sfPresetHeader(
                                achPresetName=instr['name'].encode('ascii'),
                                wPreset=len(phdr),
                                wBank=0,
                                wPresetBagNdx=len(pbag),
                                dwLibrary=0,
                                dwGenre=0,
                                dwMorphology=0,
                            ))

                            pbag.append(sfPresetBag(
                                wGenNdx=len(pgen),
                                wModNdx=len(pmod),
                            ))

                            pgen.append(sfGenList(
                                sfGenOper=41, # instrument
                                genAmount=len(inst),
                            ))

                            inst.append(sfInst(
                                achInstName=instr['name'].encode('ascii'),
                                wInstBagNdx=len(ibag),
                            ))

                            ibag.append(sfInstBag(
                                wInstGenNdx=len(igen),
                                wInstModNdx=len(imod),
                            ))

                            igen.append(sfInstGenList(
                                sfGenOper=53, # sampleID
                                genAmount=len(shdr),
                            ))

                            shdr.append(sfSample(
                                achSampleName=instr['name'].encode('ascii'),
                                dwStart=sample_offset,
                                dwEnd=sample_offset + num_frames,
                                dwStartloop=0,
                                dwEndloop=0,
                                dwSampleRate=wfp.getframerate(),
                                byOriginalPitch=60,
                                chPitchCorrection=0,
                                wSampleLink=0,
                                sfSampleType=1, # mono
                            ))

                            for _ in range(num_frames):
                                writer.write(wfp.readframes(1))
                                sample_offset += 1
                            for _ in range(46):
                                writer.write(struct.pack('<h', 0))
                                sample_offset += 1

            phdr.append(sfPresetHeader(
                achPresetName=b'EOP',
                wPreset=0,
                wBank=0,
                wPresetBagNdx=len(pbag),
                dwLibrary=0,
                dwGenre=0,
                dwMorphology=0,
            ))

            pbag.append(sfPresetBag(
                wGenNdx=len(pgen),
                wModNdx=len(pmod),
            ))

            pmod.append(sfModList(
                sfModSrcOper=0,
                sfModDestOper=0,
                modAmount=0,
                sfModAmtSrcOper=0,
                sfModTransOper=0,
            ))

            pgen.append(sfGenList(
                sfGenOper=0,
                genAmount=0,
            ))

            inst.append(sfInst(
                achInstName=b'EOI',
                wInstBagNdx=len(ibag),
            ))

            ibag.append(sfInstBag(
                wInstGenNdx=len(igen),
                wInstModNdx=len(imod),
            ))

            imod.append(sfModList(
                sfModSrcOper=0,
                sfModDestOper=0,
                modAmount=0,
                sfModAmtSrcOper=0,
                sfModTransOper=0,
            ))

            igen.append(sfInstGenList(
                sfGenOper=0,
                genAmount=0,
            ))

            shdr.append(sfSample(
                achSampleName=b'EOS',
                dwStart=0,
                dwEnd=0,
                dwStartloop=0,
                dwEndloop=0,
                dwSampleRate=0,
                byOriginalPitch=0,
                chPitchCorrection=0,
                wSampleLink=0,
                sfSampleType=0,
            ))

            with writer.list('pdta'):
                with writer.chunk('phdr'):
                    for s in phdr:
                        writer.write(s.pack())

                with writer.chunk('pbag'):
                    for s in pbag:
                        writer.write(s.pack())

                with writer.chunk('pmod'):
                    for s in pmod:
                        writer.write(s.pack())

                with writer.chunk('pgen'):
                    for s in pgen:
                        writer.write(s.pack())

                with writer.chunk('inst'):
                    for s in inst:
                        writer.write(s.pack())

                with writer.chunk('ibag'):
                    for s in ibag:
                        writer.write(s.pack())

                with writer.chunk('imod'):
                    for s in imod:
                        writer.write(s.pack())

                with writer.chunk('igen'):
                    for s in igen:
                        writer.write(s.pack())

                with writer.chunk('shdr'):
                    for s in shdr:
                        writer.write(s.pack())


    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
