from cpython.ref cimport PyObject
from libc cimport stdlib
from libc cimport string


cdef char* allocstr(str s):
    cdef char* r
    b = s.encode('utf-8')
    r = <char*>stdlib.malloc(len(b) + 1)
    string.strcpy(r, b)
    return r


cdef class URID_Map_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#map'

    def __cinit__(self, URID_Mapper mapper):
        self.data.handle = <PyObject*>mapper
        self.data.map = self.urid_map

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri) except -1:
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
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid) except <const char*>-1:
        cdef URID_Mapper mapper = <URID_Mapper>handle
        return mapper.unmap(urid)


cdef class URID_Mapper(object):
    def __init__(self):
        pass

    cpdef LV2_URID map(self, const char* uri) except -1:
        raise NotImplementedError

    cdef const char* unmap(self, LV2_URID urid) except <const char*>-1:
        raise NotImplementedError


cdef class URID_StaticMapper(URID_Mapper):
    def __init__(self):
        URID_Mapper.__init__(self)
        self.url_map = {}
        self.url_reverse_map = {}
        self.__next_urid = 100

        self.__insert(b'http://lv2plug.in/ns/ext/midi#MidiEvent')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#frameTime')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Blank')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Bool')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Chunk')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Double')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Float')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Int')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Long')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Literal')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Object')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Path')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Property')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Resource')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Sequence')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#String')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Tuple')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#URI')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#URID')
        self.__insert(b'http://lv2plug.in/ns/ext/atom#Vector')

    cdef LV2_URID __insert(self, const char* uri) except -1:
        assert bytes(uri) not in self.url_map
        urid = self.url_map[uri] = self.__next_urid
        self.url_reverse_map[urid] = bytes(uri)
        self.__next_urid += 1
        return urid

    cpdef LV2_URID map(self, const char* uri) except -1:
        return self.url_map[uri]

    cpdef const char* unmap(self, LV2_URID urid) except <const char*>-1:
        try:
            return self.url_reverse_map[urid]
        except KeyError:
            return NULL

static_mapper = URID_StaticMapper()


cdef class URID_DynamicMapper(URID_StaticMapper):
    def __init__(self):
        URID_StaticMapper.__init__(self)
        self.next_urid = 1000

    cpdef LV2_URID map(self, const char* uri) except -1:
        try:
            urid = URID_StaticMapper.map(self, uri)
        except KeyError:
            urid = self.url_map[uri] = self.next_urid
            self.url_reverse_map[urid] = bytes(uri)
            self.next_urid += 1

        return urid
