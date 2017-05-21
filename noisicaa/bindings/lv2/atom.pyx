
import contextlib
import logging

logger = logging.getLogger(__name__)


cdef class AtomForge(object):
    def __cinit__(self, URID_Mapper mapper):
        self.map = URID_Map_Feature(mapper)

        self.midi_event = mapper.map(
            b'http://lv2plug.in/ns/ext/midi#MidiEvent')
        self.frame_time = mapper.map(
            b'http://lv2plug.in/ns/ext/atom#frameTime')

        lv2_atom_forge_init(&self.forge, &self.map.data)

    def set_buffer(self, uint8_t* buf, size_t size):
        lv2_atom_forge_set_buffer(&self.forge, buf, size)

    @property
    def bytes_written(self):
        return int(self.forge.offset)

    @contextlib.contextmanager
    def sequence(self):
        cdef LV2_Atom_Forge_Frame frame
        lv2_atom_forge_sequence_head(&self.forge, &frame, self.frame_time)
        yield
        lv2_atom_forge_pop(&self.forge, &frame)

    def write_midi_event(self, uint32_t time, const uint8_t* msg, uint32_t length):
        lv2_atom_forge_frame_time(&self.forge, time)
        lv2_atom_forge_atom(&self.forge, length, self.midi_event)
        lv2_atom_forge_write(&self.forge, msg, length)
