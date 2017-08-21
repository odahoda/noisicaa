from libcpp cimport bool
from libcpp.string cimport string

cdef extern from "status.h" namespace "noisicaa" nogil:
    cppclass Status:
        bool is_error() const
        string message() const