
cdef class PyBufferType(object):
    pass

cdef class PyFloat(PyBufferType):
    def __init__(self):
        self.cpptype.reset(new Float())

    def __str__(self):
        return 'Float'


cdef class PyFloatAudioBlock(PyBufferType):
    def __init__(self):
        self.cpptype.reset(new FloatAudioBlock())

    def __str__(self):
        return 'FloatAudioBlock'


cdef class PyAtomData(PyBufferType):
    def __init__(self):
        self.cpptype.reset(new AtomData())

    def __str__(self):
        return 'AtomData'
