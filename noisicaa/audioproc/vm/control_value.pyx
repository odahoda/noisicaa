import enum

class PyControlValueType(enum.Enum):
    Float = ControlValueType.FloatCV
    Int = ControlValueType.IntCV


cdef class PyControlValue(object):
    cdef ControlValue* ptr(self):
        return self.__cv

    cdef ControlValue* release(self):
        return self.__cv_ptr.release()

    @property
    def name(self):
        return bytes(self.__cv.name()).decode('utf-8')


cdef class PyFloatControlValue(PyControlValue):
    def __init__(self, name, value):
        self.__cv_ptr.reset(new FloatControlValue(name.encode('utf-8'), value))
        self.__cv = self.__cv_ptr.get()

    @property
    def value(self):
        cdef FloatControlValue* cv = <FloatControlValue*>self.__cv;
        return float(cv.value())

    @value.setter
    def value(self, v):
        cdef FloatControlValue* cv = <FloatControlValue*>self.__cv;
        cv.set_value(<float>v)


cdef class PyIntControlValue(PyControlValue):
    def __init__(self, name, value):
        self.__cv_ptr.reset(new IntControlValue(name.encode('utf-8'), value))
        self.__cv = self.__cv_ptr.get()

    @property
    def value(self):
        cdef IntControlValue* cv = <IntControlValue*>self.__cv;
        return int(cv.value())

    @value.setter
    def value(self, v):
        cdef IntControlValue* cv = <IntControlValue*>self.__cv;
        cv.set_value(<int64_t>v)

