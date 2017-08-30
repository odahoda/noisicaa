from noisicaa.bindings.lv2.urid cimport *
from .status cimport *

cdef extern from "host_data.h" namespace "noisicaa" nogil:
    cppclass HostData:
        Status setup()
        Status setup_lilv()
        Status setup_lv2()

        LV2_URID_Map* lv2_urid_map;
        LV2_URID_Unmap* lv2_urid_unmap;
