from libcpp cimport bool
from libcpp.string cimport string

cdef extern from "status.h" namespace "noisicaa" nogil:
    cppclass Status:
        bool is_error() const
        string message() const

        @staticmethod
        Status Ok()

        @staticmethod
        Status Error(const string& message)

    cppclass StatusOr[T](Status):
        T result() const
