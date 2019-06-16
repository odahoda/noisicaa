# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

from libc.stdint cimport uint8_t

import contextlib
import logging

logger = logging.getLogger(__name__)


cdef class Event(object):
    def __init__(self, int64_t frames, Atom atom):
        self.frames = frames
        self.atom = atom

    def __str__(self):
        return '<Event frames=%d>%s</Event>' % (self.frames, self.atom)
    __repr__ = __str__


cdef class Atom(object):
    def __cinit__(self, PyURIDMapper mapper):
        self.mapper = mapper
        self.atom = NULL

    cdef init(self, LV2_Atom* atom):
        self.atom = atom
        return self

    @staticmethod
    cdef Atom wrap(PyURIDMapper mapper, uint8_t* buf):
        cdef LV2_Atom* atom = <LV2_Atom*>buf
        return Atom(mapper).init(atom)

    def __str__(self):
        return '<Atom type="%s" size=%d>' % (self.type_uri, self.size)
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

    @property
    def as_object(self):
        type_uri = self.type_uri
        if type_uri == 'http://lv2plug.in/ns/ext/atom#Object':
            d = {}
            for key, value in self.items():
                d[self.mapper.unmap(key)] = value.as_object
            return d

        elif type_uri == 'http://lv2plug.in/ns/ext/atom#Tuple':
            return tuple(t.as_object for t in self.tuple)

        elif type_uri == 'http://lv2plug.in/ns/ext/atom#Float':
            return self.float

        elif type_uri == 'http://lv2plug.in/ns/ext/atom#Int':
            return self.int

        elif type_uri == 'http://lv2plug.in/ns/ext/atom#String':
            return self.str

        elif type_uri == 'http://lv2plug.in/ns/ext/midi#MidiEvent':
            return self.data

        else:
            raise ValueError('%r (%r)' % (type_uri, self.type_urid))

    @property
    def int(self):
        return int((<LV2_Atom_Int*>self.atom).body)

    @property
    def float(self):
        return float((<LV2_Atom_Float*>self.atom).body)

    @property
    def str(self):
        cdef LV2_Atom_String* s = <LV2_Atom_String*>self.atom
        cdef uint8_t* body = (<uint8_t*>s) + sizeof(LV2_Atom_String)
        return bytes(body[:s.atom.size-1]).decode('utf-8')

    @property
    def tuple(self):
        cdef LV2_Atom_Tuple* tup = <LV2_Atom_Tuple*>self.atom
        cdef uint8_t* body = (<uint8_t*>tup) + sizeof(LV2_Atom_Tuple)
        cdef uint32_t size = tup.atom.size

        cdef LV2_Atom* it = lv2_atom_tuple_begin(tup)
        while not lv2_atom_tuple_is_end(body, size, it):
            yield Atom.wrap(self.mapper, <uint8_t*>it)
            it = lv2_atom_tuple_next(it)

    @property
    def sequence(self):
        cdef LV2_Atom_Sequence* seq = <LV2_Atom_Sequence*>self.atom

        cdef LV2_Atom_Event* event
        event = lv2_atom_sequence_begin(&seq.body)
        while not lv2_atom_sequence_is_end(&seq.body, seq.atom.size, event):
            yield Event(event.time.frames, Atom.wrap(self.mapper, <uint8_t*>&event.body))
            event = lv2_atom_sequence_next(event)

    @property
    def object_urid(self):
        cdef LV2_Atom_Object* obj = <LV2_Atom_Object*>self.atom
        return obj.body.id

    @property
    def object_uri(self):
        return self.mapper.unmap(self.object_urid)

    def items(self):
        cdef LV2_Atom_Object* obj = <LV2_Atom_Object*>self.atom

        cdef LV2_Atom_Property_Body* it = lv2_atom_object_begin(&obj.body)
        while not lv2_atom_object_is_end(&obj.body, obj.atom.size, it):
            yield (it.key, Atom.wrap(self.mapper, <uint8_t*>&it.value))
            it = lv2_atom_object_next(it)


def wrap_atom(mapper, buf):
    cdef uint8_t* ptr
    cdef char[:] view
    if isinstance(buf, memoryview):
        view = buf
        ptr = <uint8_t*>(&view[0])
    elif isinstance(buf, (bytes, bytearray)):
        ptr = <uint8_t*>buf
    else:
        raise TypeError(type(buf))

    return Atom.wrap(mapper, ptr)


cdef class AtomForge(object):
    def __cinit__(self, PyURIDMapper mapper):
        self.map = URID_Map_Feature(mapper)

        self.midi_event = mapper.map(
            'http://lv2plug.in/ns/ext/midi#MidiEvent')
        self.frame_time = mapper.map(
            'http://lv2plug.in/ns/ext/atom#frameTime')

        lv2_atom_forge_init(&self.forge, &self.map.data)

    cpdef set_buffer(self, uint8_t[:] buf, size_t size):
        lv2_atom_forge_set_buffer(&self.forge, &buf[0], size)

    @property
    def bytes_written(self):
        return int(self.forge.offset)

    @contextlib.contextmanager
    def sequence(self):
        cdef LV2_Atom_Forge_Frame frame
        lv2_atom_forge_sequence_head(&self.forge, &frame, self.frame_time)
        yield
        lv2_atom_forge_pop(&self.forge, &frame)

    @contextlib.contextmanager
    def object(self, LV2_URID id=0, LV2_URID otype=0):
        cdef LV2_Atom_Forge_Frame frame
        lv2_atom_forge_object(&self.forge, &frame, id, otype)
        yield
        lv2_atom_forge_pop(&self.forge, &frame)

    @contextlib.contextmanager
    def tuple(self):
        cdef LV2_Atom_Forge_Frame frame
        lv2_atom_forge_tuple(&self.forge, &frame)
        yield
        lv2_atom_forge_pop(&self.forge, &frame)

    def write_key(self, LV2_URID key):
        lv2_atom_forge_key(&self.forge, key)

    def write_frame_time(self, uint32_t time):
        lv2_atom_forge_frame_time(&self.forge, time)

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

    def write_string(self, str value):
        cdef bytes b_value = value.encode('utf-8')
        lv2_atom_forge_string(&self.forge, b_value, len(b_value))

    def write_int(self, int value):
        lv2_atom_forge_int(&self.forge, value)

    def write_bool(self, bool value):
        lv2_atom_forge_bool(&self.forge, value)

    def write_double(self, float value):
        lv2_atom_forge_double(&self.forge, value)

    # @classmethod
    # def build_midi_atom(cls, bytes msg):
    #     forge = cls(urid.get_static_mapper())
    #     buf = bytearray(1024)
    #     forge.set_buffer(buf, 1024)
    #     forge.write_midi_atom(msg, len(msg))
    #     return bytes(buf[:forge.bytes_written])

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
