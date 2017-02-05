from cpython.ref cimport PyObject
from libc.stdint cimport uint32_t
from libc cimport stdlib
from libc cimport string
cimport numpy

import contextlib
import logging
import operator
import numpy

logger = logging.getLogger(__name__)


cdef char* allocstr(str s):
    cdef char* r
    b = s.encode('utf-8')
    r = <char*>stdlib.malloc(len(b) + 1)
    string.strcpy(r, b)
    return r


cdef class Feature(object):
    cdef LV2_Feature* create_lv2_feature(self):
        return <LV2_Feature*>stdlib.calloc(sizeof(LV2_Feature), 1)


cdef class URID_Map_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#map'

    def __init__(self, URID_Mapper mapper):
        self.data.handle = <PyObject*>mapper
        self.data.map = mapper.urid_map

    cdef LV2_Feature* create_lv2_feature(self):
        cdef LV2_Feature* feature = Feature.create_lv2_feature(self)
        feature.URI = allocstr(self.uri)
        feature.data = &self.data
        return feature


cdef class URID_Unmap_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#unmap'

    def __init__(self, URID_Mapper mapper):
        self.data.handle = <PyObject*>mapper
        self.data.unmap = mapper.urid_unmap

    cdef LV2_Feature* create_lv2_feature(self):
        cdef LV2_Feature* feature = Feature.create_lv2_feature(self)
        feature.URI = allocstr(self.uri)
        feature.data = &self.data
        return feature


cdef class URID_Mapper(object):
    def __init__(self):
        self.url_map = {}
        self.url_reverse_map = {}
        self.next_urid = 100

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri):
        cdef URID_Mapper self = <URID_Mapper>handle

        try:
            urid = self.url_map[uri]
        except KeyError:
            urid = self.url_map[uri] = self.next_urid
            self.url_reverse_map[urid] = bytes(uri)
            self.next_urid += 1

        return urid

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid):
        cdef URID_Mapper self = <URID_Mapper>handle

        try:
            return self.url_reverse_map[urid]
        except KeyError:
            return NULL


cdef class AtomForge(object):
    def __cinit__(self, URID_Mapper mapper):
        self.map.handle = <PyObject*>mapper
        self.map.map = mapper.urid_map

        self.midi_event = self.map.map(
            self.map.handle, b'http://lv2plug.in/ns/ext/midi#MidiEvent')
        self.frame_time = self.map.map(
            self.map.handle, b'http://lv2plug.in/ns/ext/atom#frameTime')

        lv2_atom_forge_init(&self.forge, &self.map)

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
