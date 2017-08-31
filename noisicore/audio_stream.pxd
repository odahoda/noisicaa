from libcpp.string cimport string

from .status cimport *

cdef extern from "audio_stream.h" namespace "noisicaa" nogil:
    cppclass AudioStreamBase:
        Status setup()
        void cleanup()

        string address() const

        void close()
        StatusOr[string] receive_block_bytes()
        StatusOr[string] receive_block()
        Status send_block_bytes(const string& block_bytes)
        Status send_block(const string& block)


    cppclass AudioStreamServer(AudioStreamBase):
        AudioStreamServer(const string& address);

        Status setup();
        void cleanup();


    cppclass AudioStreamClient(AudioStreamBase):
        AudioStreamClient(const string& address);

        Status setup();
        void cleanup();
