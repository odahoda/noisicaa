from .status cimport *
from .spec cimport *

cdef extern from "vm.h" namespace "noisicaa" nogil:
    cppclass VM:
        Status setup()
        Status cleanup()
        Status set_spec(const Spec& spec)
        Status process_frame()
