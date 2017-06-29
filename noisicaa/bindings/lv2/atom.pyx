
import contextlib
import logging

from . import urid

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

    def write_raw_event(self, uint32_t time, const uint8_t* atom, uint32_t length):
        lv2_atom_forge_frame_time(&self.forge, time)
        lv2_atom_forge_write(&self.forge, atom, length)

    def write_raw(self, const uint8_t* atom, uint32_t length):
        lv2_atom_forge_write(&self.forge, atom, length)

    def write_atom_event(self, uint32_t time, LV2_URID type, const uint8_t* data, uint32_t length):
        lv2_atom_forge_frame_time(&self.forge, time)
        lv2_atom_forge_atom(&self.forge, length, type)
        lv2_atom_forge_write(&self.forge, data, length)

    def write_atom(self, LV2_URID type, const uint8_t* data, uint32_t length):
        lv2_atom_forge_atom(&self.forge, length, type)
        lv2_atom_forge_write(&self.forge, data, length)

    def write_midi_event(self, uint32_t time, const uint8_t* msg, uint32_t length):
        lv2_atom_forge_frame_time(&self.forge, time)
        self.write_midi_atom(msg, length)

    def write_midi_atom(self, const uint8_t* msg, uint32_t length):
        lv2_atom_forge_atom(&self.forge, length, self.midi_event)
        lv2_atom_forge_write(&self.forge, msg, length)

    @classmethod
    def build_midi_atom(cls, bytes msg):
        forge = cls(urid.static_mapper)
        buf = bytearray(1024)
        forge.set_buffer(buf, 1024)
        forge.write_midi_atom(msg, len(msg))
        return bytes(buf[:forge.bytes_written])

    @classmethod
    def build_midi_noteon(cls, channel, pitch, velocity):
        assert 0 <= channel < 16, channel
        assert 0 <= pitch < 128, pitch
        assert 0 <= velocity < 128, velocity
        return cls.build_midi_atom(bytes([0x90 + channel, pitch, velocity]))

    @classmethod
    def build_midi_noteoff(cls, channel, pitch):
        assert 0 <= channel < 16, channel
        assert 0 <= pitch < 128, pitch
        return cls.build_midi_atom(bytes([0x80 + channel, pitch, 0]))


cdef class Atom(object):
    def __cinit__(self, URID_Mapper mapper):
        self.mapper = mapper
        self.atom = NULL

    cdef init(self, LV2_Atom* atom):
        self.atom = atom
        return self

    def __str__(self):
        return '<Atom type="%s" size=%d>' % (self.type_uri.decode('utf-8'), self.size)
    __repr__ = __str__

    @property
    def type_urid(self):
        return self.atom.type

    @property
    def type_uri(self):
        return self.mapper.unmap(self.type_urid)

    @property
    def size(self):
        return self.atom.size

    @property
    def data(self):
        cdef uint8_t* d = <uint8_t*>self.atom + sizeof(LV2_Atom)
        return bytes(d[:self.size])

    @property
    def as_bytes(self):
        cdef uint8_t* d = <uint8_t*>self.atom
        return bytes(d[:sizeof(LV2_Atom) + self.size])


cdef class MidiEvent(Atom):
    def __str__(self):
        return '<MidiEvent>%s</MidiEvent>' % ' '.join('%02x' % b for b in self.data)
    __repr__ = __str__


cdef class Event(object):
    def __init__(self, int64_t frames, Atom atom):
        self.frames = frames
        self.atom = atom

    def __str__(self):
        return '<Event frames=%d>%s</Event>' % (self.frames, self.atom)
    __repr__ = __str__


cdef class Sequence(Atom):
    def __str__(self):
        return '<Sequence>%s</Sequence>' % ''.join(str(e) for e in self.events)
    __repr__ = __str__

    @property
    def events(self):
        result = []
        cdef LV2_Atom_Sequence* seq = <LV2_Atom_Sequence*>self.atom

        cdef LV2_Atom_Event* event
        event = lv2_atom_sequence_begin(&seq.body)
        while not lv2_atom_sequence_is_end(&seq.body, seq.atom.size, event):
            result.append(
                Event(event.time.frames, wrap_atom(self.mapper, <uint8_t*>&event.body)))
            event = lv2_atom_sequence_next(event)
        return result


cpdef wrap_atom(URID_Mapper mapper, uint8_t* buf):
    cdef LV2_Atom* atom = <LV2_Atom*>buf
    type_uri = mapper.unmap(atom.type)
    if type_uri == b'http://lv2plug.in/ns/ext/atom#Sequence':
        return Sequence(mapper).init(atom)
    elif type_uri == b'http://lv2plug.in/ns/ext/midi#MidiEvent':
        return MidiEvent(mapper).init(atom)
    else:
        return Atom(mapper).init(atom)
