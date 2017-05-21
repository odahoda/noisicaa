from libc cimport stdlib
from libc cimport string


cdef char* allocstr(str s):
    cdef char* r
    b = s.encode('utf-8')
    r = <char*>stdlib.malloc(len(b) + 1)
    string.strcpy(r, b)
    return r


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
