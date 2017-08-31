from libcpp.memory cimport unique_ptr
from libcpp.string cimport string


class Error(Exception):
    pass


cdef class AudioStream(object):
    cdef unique_ptr[AudioStreamBase] stream

    def __init__(self):
        raise TypeError("Instances must be created with create_server/create_client.")

    @classmethod
    def create_server(self, const string& address):
        cdef AudioStream obj = AudioStream.__new__(AudioStream)
        obj.stream.reset(new AudioStreamServer(address))
        return obj

    @classmethod
    def create_client(self, const string& address):
        cdef AudioStream obj = AudioStream.__new__(AudioStream)
        obj.stream.reset(new AudioStreamClient(address))
        return obj

    def setup(self):
        cdef AudioStreamBase* stream = self.stream.get()

        cdef Status status
        with nogil:
            status = stream.setup()
        if status.is_error():
            raise Error(status.message())

    def cleanup(self):
        cdef AudioStreamBase* stream = self.stream.get()
        with nogil:
            stream.cleanup()

    def close(self):
        cdef AudioStreamBase* stream = self.stream.get()
        with nogil:
            stream.close()

    def receive_block_bytes(self):
        cdef AudioStreamBase* stream = self.stream.get()

        cdef StatusOr[string] status_or_bytes
        with nogil:
            status_or_bytes = stream.receive_block_bytes();

        if status_or_bytes.is_error():
            raise Error(status_or_bytes.message())
        return bytes(status_or_bytes.result())

    def send_block_bytes(self, const string& block_bytes):
        cdef AudioStreamBase* stream = self.stream.get()

        cdef Status status
        with nogil:
            status = stream.send_block_bytes(block_bytes);

        if status.is_error():
            raise Error(status.message())
