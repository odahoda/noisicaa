from libc.stdint cimport uint32_t

from noisicaa.core.status cimport *
from .host_data cimport *
from .block_context cimport *
from .control_value cimport *

cdef extern from "noisicaa/audioproc/vm/vm.h" namespace "noisicaa" nogil:
    cppclass Processor
    cppclass Spec
    cppclass Backend
    cppclass Buffer

    cppclass VM:
        VM(HostData* host_data)

        Status setup()
        void cleanup()
        Status add_processor(Processor* processor)
        Status add_control_value(ControlValue* cv)
        Status set_block_size(uint32_t block_size)
        Status set_spec(const Spec* spec)
        Status set_backend(Backend* backend)
        Backend* backend() const
        Status process_block(BlockContext* ctxt)
        Buffer* get_buffer(const string& name)