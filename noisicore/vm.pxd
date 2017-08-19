from .status cimport *
from .spec cimport *
from .buffers cimport *

cdef extern from "vm.h" namespace "noisicaa" nogil:
    cppclass VM:
        Status setup()
        Status cleanup()
        Status set_spec(const Spec* spec)
        Status process_frame()
        Buffer* get_buffer(const string& name)
