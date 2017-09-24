from libcpp.string cimport string

from noisicaa.core.status cimport *

cdef extern from "noisicaa/audioproc/vm/audio_stream.h" namespace "noisicaa" nogil:
    cppclass AudioStreamBase:
        Status setup()
        void cleanup()

        string address() const

        void close()
        StatusOr[string] receive_bytes()
        Status send_bytes(const string& block_bytes)


    cppclass AudioStreamServer(AudioStreamBase):
        AudioStreamServer(const string& address);

        Status setup();
        void cleanup();


    cppclass AudioStreamClient(AudioStreamBase):
        AudioStreamClient(const string& address);

        Status setup();
        void cleanup();
