#!/usr/bin/python3

from . import model
from . import state


class Instrument(model.Instrument, state.StateBase):
    def __init__(self, name=None, collection=None, state=None):
        super().__init__(state)
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
        json = dict((k, v) for k, v in json.items() if k != '__type__')
        if instr_type == 'SoundFont':
            instr = SoundFontInstrument(**json)
        elif instr_type == 'Sample':
            instr = SampleInstrument(**json)
        else:
            raise ValueError("Bad instrument type %s" % instr_type)
        return instr

state.StateBase.register_class(Instrument)


class SoundFontInstrument(model.SoundFontInstrument, Instrument):
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

state.StateBase.register_class(SoundFontInstrument)
Instrument.register_subclass(SoundFontInstrument)


class SampleInstrument(model.SampleInstrument, Instrument):
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

state.StateBase.register_class(SampleInstrument)
Instrument.register_subclass(SampleInstrument)


