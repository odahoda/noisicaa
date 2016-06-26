#!/usr/bin/python3

from noisicaa import core


class Instrument(core.ObjectBase):
    name = core.Property(str)
    collection = core.ObjectReferenceProperty(allow_none=True)


class SoundFontInstrument(Instrument):
    path = core.Property(str)
    bank = core.Property(int)
    preset = core.Property(int)


class SampleInstrument(Instrument):
    path = core.Property(str)
