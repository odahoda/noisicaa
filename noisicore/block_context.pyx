

cdef class PyBlockContext(object):
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

    cdef BlockContext* ptr(self):
        return &self.__ctxt
