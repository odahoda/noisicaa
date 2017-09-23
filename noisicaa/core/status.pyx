
class Error(Exception):
    pass


class ConnectionClosed(Exception):
    pass


cdef int check(const Status& status) nogil except -1:
    if status.is_connection_closed():
        with gil:
            raise ConnectionClosed()
    if status.is_error():
        with gil:
            raise Error(status.message())
    return 0

