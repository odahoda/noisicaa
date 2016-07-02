#!/usr/bin/python3

import glob
import os.path
import logging

from noisicaa import core
#from ..ui_state import UIState
from .soundfont import SoundFont
from noisicaa.music import state


# TODO:
# - removing instruments from collection, hides it
# - removing collection removes all instruments
# - make UI
# - UI actions use commands

logger = logging.getLogger(__name__)

class Error(Exception):
    pass


# class Collection(state.StateBase):
#     name = core.Property(str)

#     def __init__(self, name=None, state=None):
#         super().__init__(state)
#         if state is None:
#             self.name = name


# class SoundFontCollection(Collection):
#     path = core.Property(str)

#     def __init__(self, name=None, path=None, state=None):
#         super().__init__(name, state)
#         if state is None:
#             self.path = path

#     def create_instruments(self):
#         sf = SoundFont()
#         sf.parse(self.path)
#         for preset in sf.presets:
#             yield SoundFontInstrument(
#                 preset.name, self, self.path, preset.bank, preset.preset)

# Collection.register_subclass(SoundFontCollection)


# class InstrumentLibrary(state.StateBase):
#     #ui_state = core.ObjectProperty(UIState)
#     instruments = core.ObjectListProperty(Instrument)
#     collections = core.ObjectListProperty(Collection)

#     def __init__(self, state=None, add_default_instruments=True):
#         super().__init__(state)
#         if state is None and add_default_instruments:
#             for p in glob.glob('/usr/share/sounds/sf2/*.sf2'):
#                 self.add_soundfont(p)

#         # if self.ui_state is None:
#         #     self.ui_state = UIState()

#         self.set_root()

#     def add_instrument(self, instr):
#         self.instruments.append(instr)

#     def add_soundfont(self, path):
#         sf = SoundFont()
#         sf.parse(path)
#         collection = SoundFontCollection(sf.bank_name, path)
#         self.collections.append(collection)
#         for instr in collection.create_instruments():
#             self.add_instrument(instr)

#     def add_sample(self, path):
#         instr = SampleInstrument(
#             os.path.splitext(os.path.basename(path))[0], path)
#         self.add_instrument(instr)
