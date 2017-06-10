
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
        return bytes(d[0:self.size])


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
