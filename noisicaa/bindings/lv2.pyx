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
    pass


cdef class URID_Map_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#map'

    def __cinit__(self, URID_Mapper mapper):
        self.data.handle = <PyObject*>mapper
        self.data.map = self.urid_map

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri):
        cdef URID_Mapper mapper = <URID_Mapper>handle
        return mapper.map(uri)


cdef class URID_Unmap_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#unmap'

    def __cinit__(self, URID_Mapper mapper):
        self.data.handle = <PyObject*>mapper
        self.data.unmap = self.urid_unmap

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid):
        cdef URID_Mapper mapper = <URID_Mapper>handle
        return mapper.unmap(urid)


cdef class URID_Mapper(object):
    def __init__(self):
        self.url_map = {}
        self.url_reverse_map = {}
        self.next_urid = 100

    cdef LV2_URID map(self, const char* uri):
        try:
            urid = self.url_map[uri]
        except KeyError:
            urid = self.url_map[uri] = self.next_urid
            self.url_reverse_map[urid] = bytes(uri)
            self.next_urid += 1

        return urid

    cdef const char* unmap(self, LV2_URID urid):
        try:
            return self.url_reverse_map[urid]
        except KeyError:
            return NULL


cdef class Options_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/options#options'

    def __cinit__(self, URID_Mapper mapper):
        self.mapper = mapper

        self.sample_rate = 44100
        self.min_block_length = 32
        self.max_block_length = 2**16
        self.midi_buf_size = 4096

        self.urid_atom_Float = self.mapper.map(
            b'http://lv2plug.in/ns/ext/atom#Float')
        self.urid_atom_Int = self.mapper.map(
            b'http://lv2plug.in/ns/ext/atom#Int')
        self.urid_param_sampleRate = self.mapper.map(
            b'http://lv2plug.in/ns/ext/parameters#sampleRate')
        self.urid_bufsz_minBlockLength = self.mapper.map(
            b'http://lv2plug.in/ns/ext/buf-size#minBlockLength')
        self.urid_bufsz_maxBlockLength = self.mapper.map(
            b'http://lv2plug.in/ns/ext/buf-size#maxBlockLength')
        self.urid_bufsz_sequenceSize = self.mapper.map(
            b'http://lv2plug.in/ns/ext/buf-size#sequenceSize')

        cdef LV2_Options_Option* option;
        cdef int idx = 0

        option = &self.options[idx]
        option.context = LV2_OPTIONS_INSTANCE
        option.subject = 0
        option.key = self.urid_param_sampleRate
        option.size = sizeof(float)
        option.type = self.urid_atom_Float
        option.value = &self.sample_rate
        idx += 1

        option = &self.options[idx]
        option.context = LV2_OPTIONS_INSTANCE
        option.subject = 0
        option.key = self.urid_bufsz_minBlockLength
        option.size = sizeof(int32_t)
        option.type = self.urid_atom_Int
        option.value = &self.min_block_length
        idx += 1

        option = &self.options[idx]
        option.context = LV2_OPTIONS_INSTANCE
        option.subject = 0
        option.key = self.urid_bufsz_maxBlockLength
        option.size = sizeof(int32_t)
        option.type = self.urid_atom_Int
        option.value = &self.max_block_length
        idx += 1

        option = &self.options[idx]
        option.context = LV2_OPTIONS_INSTANCE
        option.subject = 0
        option.key = self.urid_bufsz_sequenceSize
        option.size = sizeof(int32_t)
        option.type = self.urid_atom_Int
        option.value = &self.midi_buf_size
        idx += 1

        option = &self.options[idx]
        option.context = LV2_OPTIONS_INSTANCE
        option.subject = 0
        option.key = 0
        option.size = 0
        option.type = 0
        option.value = NULL

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.options[0]


cdef class BufSize_BoundedBlockLength_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/buf-size#boundedBlockLength'

    def __init__(self):
        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = NULL


cdef class BufSize_PowerOf2BlockLength_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/buf-size#powerOf2BlockLength'

    def __init__(self):
        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = NULL


cdef class Worker_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/worker#schedule'

    def __cinit__(self):
        self.data.handle = <PyObject*>self
        self.data.schedule_work = self.schedule_work

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef LV2_Worker_Status schedule_work(
        LV2_Worker_Schedule_Handle handle, uint32_t size, const void* data):
        cdef Worker_Feature self = <Worker_Feature>handle
        logger.info("schedule_work(%d, %d)", size, <int>data)
        return LV2_WORKER_ERR_UNKNOWN


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
