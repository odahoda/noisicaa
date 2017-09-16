from .status cimport *

cdef class PyHostData(object):
    def __init__(self):
        self.__host_data_ptr.reset(new HostData())
        self.__host_data = self.__host_data_ptr.get()

    def setup(self):
        # TODO: move this to C++ code
        self.__mapper = get_static_mapper()
        self.__map_feature = URID_Map_Feature(self.__mapper)
        self.__unmap_feature = URID_Unmap_Feature(self.__mapper)

        cdef LV2SubSystem* lv2 = self.__host_data.lv2.get()
        lv2.urid_map = &self.__map_feature.data
        lv2.urid_unmap = &self.__unmap_feature.data

        check(self.__host_data.setup())

    def cleanup(self):
        self.__host_data.cleanup()

    cdef HostData* ptr(self):
        return self.__host_data
