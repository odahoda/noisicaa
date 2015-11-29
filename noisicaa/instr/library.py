#!/usr/bin/python3

import glob
import os.path
import logging

from noisicaa import core
from ..ui_state import UIState
from .soundfont import SoundFont


# TODO:
# - removing instruments from collection, hides it
# - removing collection removes all instruments
# - make UI
# - UI actions use commands

logger = logging.getLogger(__name__)

class Error(Exception):
    pass


class Instrument(core.StateBase, core.CommandTarget):
    name = core.Property(str)
    collection = core.ObjectReferenceProperty(allow_none=True)

    def __init__(self, name=None, collection=None, state=None):
        super().__init__()
        self.init_state(state)
        if state is None:
            self.name = name
            self.collection = collection

    def __str__(self):
        return self.name

    def to_json(self):
        raise NotImplementedError

    @classmethod
    def from_json(cls, json):
        instr_type = json['__type__']
        del json['__type__']
        if instr_type == 'SoundFont':
            instr = SoundFontInstrument(**json)
        elif instr_type == 'Sample':
            instr = SampleInstrument(**json)
        else:
            raise ValueError("Bad instrument type %s" % instr_type)
        return instr


class SoundFontInstrument(Instrument):
    path = core.Property(str)
    bank = core.Property(int)
    preset = core.Property(int)

    def __init__(self, name=None, collection=None, path=None, bank=None, preset=None, state=None):
        super().__init__(name=name, collection=collection, state=state)
        if state is None:
            self.path = path
            self.bank = bank
            self.preset = preset

    def __str__(self):
        return '%s (%s, bank %d, preset %d)' % (
            self.name, self.path, self.bank, self.preset)

    def __eq__(self, other):
        if not isinstance(other, SoundFontInstrument):
            return False
        return (self.path, self.bank, self.preset) == (other.path, other.bank, other.preset)

    def to_json(self):
        return {
            '__type__': 'SoundFont',
            'name': self.name,
            'path': self.path,
            'bank': self.bank,
            'preset': self.preset,
        }

Instrument.register_subclass(SoundFontInstrument)


class SampleInstrument(Instrument):
    path = core.Property(str)

    def __init__(self, name=None, path=None, state=None):
        super().__init__(name=name, state=state)
        if state is None:
            self.path = path

    def __str__(self):
        return '%s (%s)' % (self.name, self.path)

    def to_json(self):
        return {
            '__type__': 'Sample',
            'name': self.name,
            'path': self.path,
        }

Instrument.register_subclass(SampleInstrument)


class Collection(core.StateBase, core.CommandTarget):
    name = core.Property(str)

    def __init__(self, name=None, state=None):
        super().__init__()
        self.init_state(state)
        if state is None:
            self.name = name


class SoundFontCollection(Collection):
    path = core.Property(str)

    def __init__(self, name=None, path=None, state=None):
        super().__init__(name, state)
        if state is None:
            self.path = path

    def create_instruments(self):
        sf = SoundFont()
        sf.parse(self.path)
        for preset in sf.presets:
            yield SoundFontInstrument(
                preset.name, self, self.path, preset.bank, preset.preset)

Collection.register_subclass(SoundFontCollection)


class InstrumentLibrary(core.StateBase, core.CommandDispatcher):
    ui_state = core.ObjectProperty(UIState)

    instruments = core.ObjectListProperty(Instrument)
    collections = core.ObjectListProperty(Collection)

    def __init__(self, state=None, add_default_instruments=True):
        super().__init__()
        self.init_state(state)

        if state is None and add_default_instruments:
            for p in glob.glob('/storage/home/share/instruments/*.sf2'):
                self.add_soundfont(p)

        if self.ui_state is None:
            self.ui_state = UIState()

        self.set_root()
        self.add_sub_target('ui_state', self.ui_state)

    def add_instrument(self, instr):
        self.instruments.append(instr)

    def add_soundfont(self, path):
        sf = SoundFont()
        sf.parse(path)
        collection = SoundFontCollection(sf.bank_name, path)
        self.collections.append(collection)
        for instr in collection.create_instruments():
            self.add_instrument(instr)

    def add_sample(self, path):
        instr = SampleInstrument(
            os.path.splitext(os.path.basename(path))[0], path)
        self.add_instrument(instr)
