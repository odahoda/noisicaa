

cdef class PyBlockContext(object):
    def __init__(self):
        self.__perf = PyPerfStats()
        self.__ctxt.perf.reset(self.__perf.release())

    cdef BlockContext* get(self) nogil:
        return &self.__ctxt

    @property
    def block_size(self):
        return int(self.__ctxt.block_size)

    @block_size.setter
    def block_size(self, value):
        self.__ctxt.block_size = <uint32_t>value

    @property
    def sample_pos(self):
        return int(self.__ctxt.sample_pos)

    @sample_pos.setter
    def sample_pos(self, value):
        self.__ctxt.sample_pos = <uint32_t>value

    @property
    def perf(self):
        return self.__perf
