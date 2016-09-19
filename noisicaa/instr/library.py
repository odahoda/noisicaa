#!/usr/bin/python3

import glob
import hashlib
import os.path
import logging

from . import soundfont

# TODO:
# - removing instruments from collection, hides it
# - removing collection removes all instruments
# - make UI
# - UI actions use commands

logger = logging.getLogger(__name__)

class Error(Exception):
    pass


class Collection(object):
    def __init__(self, name):
        self.name = name


class SoundFontCollection(Collection):
    def __init__(self, name, path):
        super().__init__(name)
        self.path = path

    def create_instruments(self):
        sf = soundfont.SoundFont()
        sf.parse(self.path)
        for preset in sf.presets:
            yield SoundFontInstrument(
                preset.name, self, self.path, preset.bank, preset.preset)


class Instrument(object):
    def __init__(self, name, collection, id):
        self.name = name
        self.collection = collection
        self.id = id


class SoundFontInstrument(Instrument):
    def __init__(self, name, collection, path, bank, preset):
        super().__init__(
            name,
            collection,
            hashlib.md5(('%s:%d:%d' % (path, bank, preset)).encode('utf-8')).hexdigest())

        self.path = path
        self.bank = bank
        self.preset = preset

    def __str__(self):
        return '<SoundFontInstrument "%s" path="%s" bank=%d preset=%d>' % (
            self.name, self.path, self.bank, self.preset)


class SampleInstrument(Instrument):
    def __init__(self, name, path):
        super().__init__(
            name,
            None,
            hashlib.md5(('%s' % path).encode('utf-8')).hexdigest())

        self.path = path

    def __str__(self):
        return '<SampleInstrument "%s" path="%s">' % (
            self.name, self.path)


class InstrumentLibrary(object):
    def __init__(self, add_default_instruments=True):
        self.instruments = []
        self.collections = []
        self.default_instrument = None

        if add_default_instruments:
            for p in sorted(glob.glob('/usr/share/sounds/sf2/*.sf2')):
                self.add_soundfont(p)

            for d in sorted(glob.glob('/storage/home/share/samples/ST-0?')):
                if not os.path.isdir(d):
                    continue

                for p in sorted(glob.glob(os.path.join(d, '*.wav'))):
                    self.add_sample(p)

        if self.default_instrument is None:
            self.default_instrument = self.instruments[0]

        logger.info("Default instrument: %s", self.default_instrument)

    def add_instrument(self, instr):
        logger.info("Adding instrument %s to library...", instr)
        self.instruments.append(instr)

    def add_soundfont(self, path):
        sf = soundfont.SoundFont()
        sf.parse(path)
        collection = SoundFontCollection(sf.bank_name, path)
        self.collections.append(collection)
        for instr in collection.create_instruments():
            self.add_instrument(instr)
            if instr.bank == 0 and instr.preset == 0 and self.default_instrument is None:
                self.default_instrument = instr

    def add_sample(self, path):
        instr = SampleInstrument(
            os.path.splitext(os.path.basename(path))[0], path)
        self.add_instrument(instr)
