
cdef extern from "noisicaa/audioproc/vm/message_queue.h" namespace "noisicaa" nogil:
    enum MessageType:
        SOUND_FILE_COMPLETE

    cppclass Message:
        MessageType type
        size_t size

    cppclass NodeMessage(Message):
        char node_id[256]

    cppclass SoundFileCompleteMessage(NodeMessage):
        pass

    cppclass MessageQueue:
        void clear()
        Message* first() const
        Message* next(Message* it) const
        int is_end(Message* it) const
