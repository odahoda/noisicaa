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

    def __cinit__(self, URIDMapper mapper):
        self.mapper = mapper

        self.data.handle = self.mapper.get()
        self.data.map = self.urid_map

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri) except -1 with gil:
        cdef urid_mapper.URIDMapper* mapper = <urid_mapper.URIDMapper*>handle
        return mapper.map(uri)


cdef class URID_Unmap_Feature(Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#unmap'

    def __cinit__(self, URIDMapper mapper):
        self.mapper = mapper

        self.data.handle = self.mapper.get()
        self.data.unmap = self.urid_unmap

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid) except <const char*>-1 with gil:
        cdef urid_mapper.URIDMapper* mapper = <urid_mapper.URIDMapper*>handle
        return mapper.unmap(urid)


cdef class URIDMapper(object):
    def __init__(self):
        pass

    cdef urid_mapper.URIDMapper* get(self):
        return self.__mapper

    cdef urid_mapper.URIDMapper* release(self):
        return self.__mapper_ptr.release()

    def map(self, uri):
        if isinstance(uri, str):
            uri = uri.encode('ascii')
        cdef LV2_URID urid = self.__mapper.map(uri)
        if urid == 0:
            raise ValueError("Failed to map uri '%s'" % uri)
        return int(urid)

    def unmap(self, urid):
        cdef const char* uri = self.__mapper.unmap(urid)
        if uri == NULL:
            raise ValueError("Failed to unmap urid %d" % urid)
        return bytes(uri).decode('ascii')


cdef class StaticURIDMapper(URIDMapper):
    def __init__(self):
        self.__mapper_ptr.reset(new urid_mapper.StaticURIDMapper())
        self.__mapper = self.__mapper_ptr.get()

static_mapper = StaticURIDMapper()

cdef URIDMapper get_static_mapper():
    return static_mapper


cdef class DynamicURIDMapper(URIDMapper):
    def __init__(self):
        self.__mapper_ptr.reset(new urid_mapper.DynamicURIDMapper())
        self.__mapper = self.__mapper_ptr.get()
