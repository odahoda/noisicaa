from libc cimport stdlib
from libc cimport string


cdef char* allocstr(str s):
    cdef char* r
    b = s.encode('utf-8')
    r = <char*>stdlib.malloc(len(b) + 1)
    string.strcpy(r, b)
    return r


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
