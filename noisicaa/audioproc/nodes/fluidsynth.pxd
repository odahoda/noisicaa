from noisicaa.bindings.lv2 cimport urid
from noisicaa.bindings cimport fluidsynth
from .. cimport node
from ..vm cimport buffers

cdef class FluidSynthSource(node.CustomNode):
    cdef str __soundfont_path
    cdef int __bank
    cdef int __preset

    cdef fluidsynth.Settings __settings
    cdef fluidsynth.Synth __synth
    cdef fluidsynth.Soundfont __sfont

    cdef buffers.Buffer __in
    cdef buffers.Buffer __out_left
    cdef buffers.Buffer __out_right

    cdef urid.URID_Mapper __mapper
    cdef urid.LV2_URID __sequence_urid
    cdef urid.LV2_URID __midi_event_urid

    cdef int connect_port(self, port_name, buf) except -1
    cdef int run(self, ctxt) except -1
