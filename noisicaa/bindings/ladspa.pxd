
cdef extern from "dlfcn.h":
    enum:
        RTLD_LAZY
        RTLD_NOW
        RTLD_GLOBAL
        RTLD_DEFAULT
        RTLD_NEXT
    void *dlopen(char *filename, int flag)
    char *dlerror()
    void *dlsym(void *handle, char *symbol)
    int dlclose(void *handle)

cdef extern from "ladspa.h" nogil:
    ctypedef float LADSPA_Data
    ctypedef void* LADSPA_Handle

    ctypedef int LADSPA_Properties
    enum:
        LADSPA_PROPERTY_REALTIME
        LADSPA_PROPERTY_INPLACE_BROKEN
        LADSPA_PROPERTY_HARD_RT_CAPABLE

    int LADSPA_IS_REALTIME(int)
    int LADSPA_IS_INPLACE_BROKEN(int)
    int LADSPA_IS_HARD_RT_CAPABLE(int)

    ctypedef int LADSPA_PortDescriptor
    enum:
        LADSPA_PORT_INPUT
        LADSPA_PORT_OUTPUT
        LADSPA_PORT_CONTROL
        LADSPA_PORT_AUDIO

    int LADSPA_IS_PORT_INPUT(int)
    int LADSPA_IS_PORT_OUTPUT(int)
    int LADSPA_IS_PORT_CONTROL(int)
    int LADSPA_IS_PORT_AUDIO(int)

    ctypedef int LADSPA_PortRangeHintDescriptor
    enum:
        LADSPA_HINT_BOUNDED_BELOW
        LADSPA_HINT_BOUNDED_ABOVE
        LADSPA_HINT_TOGGLED
        LADSPA_HINT_SAMPLE_RATE
        LADSPA_HINT_LOGARITHMIC
        LADSPA_HINT_INTEGER
        LADSPA_HINT_DEFAULT_MASK
        LADSPA_HINT_DEFAULT_NONE
        LADSPA_HINT_DEFAULT_MINIMUM
        LADSPA_HINT_DEFAULT_LOW
        LADSPA_HINT_DEFAULT_MIDDLE
        LADSPA_HINT_DEFAULT_HIGH
        LADSPA_HINT_DEFAULT_MAXIMUM
        LADSPA_HINT_DEFAULT_0
        LADSPA_HINT_DEFAULT_1
        LADSPA_HINT_DEFAULT_100
        LADSPA_HINT_DEFAULT_440

    int LADSPA_IS_HINT_BOUNDED_BELOW(int)
    int LADSPA_IS_HINT_BOUNDED_ABOVE(int)
    int LADSPA_IS_HINT_TOGGLED(int)
    int LADSPA_IS_HINT_SAMPLE_RATE(int)
    int LADSPA_IS_HINT_LOGARITHMIC(int)
    int LADSPA_IS_HINT_INTEGER(int)
    int LADSPA_IS_HINT_HAS_DEFAULT(int)
    int LADSPA_IS_HINT_DEFAULT_MINIMUM(int)
    int LADSPA_IS_HINT_DEFAULT_LOW(int)
    int LADSPA_IS_HINT_DEFAULT_MIDDLE(int)
    int LADSPA_IS_HINT_DEFAULT_HIGH(int)
    int LADSPA_IS_HINT_DEFAULT_MAXIMUM(int)
    int LADSPA_IS_HINT_DEFAULT_0(int)
    int LADSPA_IS_HINT_DEFAULT_1(int)
    int LADSPA_IS_HINT_DEFAULT_100(int)
    int LADSPA_IS_HINT_DEFAULT_440(int)

    ctypedef struct LADSPA_PortRangeHint:
        LADSPA_PortRangeHintDescriptor HintDescriptor
        LADSPA_Data LowerBound
        LADSPA_Data UpperBound

    ctypedef struct LADSPA_Descriptor:
        unsigned long UniqueID
        char* Label
        LADSPA_Properties Properties
        char* Name
        char* Maker
        char* Copyright
        unsigned long PortCount
        LADSPA_PortDescriptor* PortDescriptors
        char** PortNames
        LADSPA_PortRangeHint* PortRangeHints
        void* ImplementationData
        LADSPA_Handle (*instantiate)(void* descriptor, int sample_rate)
        void (*connect_port)(
            LADSPA_Handle Instance, unsigned long port, LADSPA_Data* data_location)
        void (*activate)(LADSPA_Handle Instance)
        void (*run)(LADSPA_Handle instance, unsigned long sample_count)
        void (*run_adding)(LADSPA_Handle instance, unsigned long sample_count)
        void (*set_run_adding_gain)(LADSPA_Handle instance, LADSPA_Data gain)
        void (*deactivate)(LADSPA_Handle instance)
        void (*cleanup)(LADSPA_Handle instance)

    LADSPA_Descriptor* ladspa_descriptor(unsigned long index)
    ctypedef LADSPA_Descriptor* (*LADSPA_Descriptor_Function)(unsigned long index)

cdef class Port(object):
    cdef LADSPA_PortDescriptor _desc
    cdef LADSPA_PortRangeHint _range_hint
    cdef int _index
    cdef const char* _name

cdef class Instance(object):
    cdef Descriptor _desc
    cdef LADSPA_Handle _handle

    cdef connect_port(self, Port port, char* data)
    cdef activate(self)
    cdef run(self, int num_samples)
    cdef deactivate(self)
    cdef cleanup(self)
    cdef close(self)

cdef class Descriptor(object):
    cdef const LADSPA_Descriptor* _desc
    cdef list _instances
    cdef readonly list ports

cdef class Library(object):
    cdef void* handle
    cdef readonly list descriptors
