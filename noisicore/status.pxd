from libcpp cimport bool
from libcpp.string cimport string

cdef extern from "noisicore/status.h" namespace "noisicaa" nogil:
    cppclass Status:
        bool is_error() const
        bool is_connection_closed() const
        bool is_os_error() const
        string message() const

        @staticmethod
        Status Ok()

        @staticmethod
        Status Error(const string& message)

    cppclass StatusOr[T](Status):
        T result() const

cdef int check(const Status& status) nogil except -1

