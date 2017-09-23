from noisicaa.core.status cimport *


cdef class PyHostData(object):
    def __init__(self):
        self.__host_data_ptr.reset(new HostData())
        self.__host_data = self.__host_data_ptr.get()

    def setup(self):
        check(self.__host_data.setup())

    def cleanup(self):
        self.__host_data.cleanup()

    cdef HostData* ptr(self):
        return self.__host_data
