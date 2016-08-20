#!/usr/bin/python3

from . import model
from . import state
from . import mutations


class Instrument(model.Instrument, state.StateBase):
    def __init__(self, name=None, library_id=None, state=None):
        super().__init__(state)
        if state is None:
            self.name = name
            self.library_id = library_id

    def __str__(self):
        return self.name

    @property
    def track(self):
        return self.parent

    @property
    def sheet(self):
        return self.track.sheet

    @property
    def project(self):
        return self.track.project

    @property
    def pipeline_node_id(self):
        return '%s-instr' % self.id

    # def add_to_pipeline(self):
    #     raise NotImplementedError

    # def remove_from_pipeline(self):
    #     raise NotImplementedError

state.StateBase.register_class(Instrument)


class SoundFontInstrument(model.SoundFontInstrument, Instrument):
    def __init__(self, name=None, library_id=None, path=None, bank=None, preset=None, state=None):
        super().__init__(name=name, library_id=library_id, state=state)
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

    def add_to_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.AddNode(
                'fluidsynth', self.pipeline_node_id, self.name,
                soundfont_path=self.path,
                bank=self.bank,
                preset=self.preset))

    def remove_from_pipeline(self):
        self.sheet.handle_pipeline_mutation(
            mutations.RemoveNode(self.pipeline_node_id))

state.StateBase.register_class(SoundFontInstrument)


class SampleInstrument(model.SampleInstrument, Instrument):
    def __init__(self, name=None, path=None, state=None):
        super().__init__(name=name, state=state)
        if state is None:
            self.path = path

    def __str__(self):
        return '%s (%s)' % (self.name, self.path)

state.StateBase.register_class(SampleInstrument)
