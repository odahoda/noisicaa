from libcpp.string cimport string

from .status cimport *

cdef extern from "audio_stream.h" namespace "noisicaa" nogil:
    cppclass AudioStreamBase:
        Status setup()
        void cleanup()

        string address() const

        void close()
        StatusOr[string] receive_frame_bytes()
        StatusOr[string] receive_frame()
        Status send_frame_bytes(const string& frame_bytes)
        Status send_frame(const string& frame)


    cppclass AudioStreamServer(AudioStreamBase):
        AudioStreamServer(const string& address);

        Status setup();
        void cleanup();


    cppclass AudioStreamClient(AudioStreamBase):
        AudioStreamClient(const string& address);

        Status setup();
        void cleanup();
