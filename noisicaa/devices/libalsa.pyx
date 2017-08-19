import errno
import logging

from . import midi_events

logger = logging.getLogger(__name__)

cdef extern from "sys/poll.h":
    cdef struct pollfd:
        int fd
        short events
        short revents

POLLIN  = 0x0001
POLLOUT = 0x0004

cdef extern from "alsa/asoundlib.h":
    ctypedef void snd_seq_t
    ctypedef void snd_seq_client_info_t
    ctypedef void snd_seq_port_info_t

    ctypedef unsigned char snd_seq_event_type_t
    ctypedef struct snd_seq_addr_t:
        unsigned char client
        unsigned char port
    ctypedef struct snd_seq_connect_t:
        snd_seq_addr_t sender
        snd_seq_addr_t dest
    ctypedef struct snd_seq_real_time_t:
        unsigned int tv_sec
        unsigned int tv_nsec
    ctypedef unsigned int snd_seq_tick_time_t
    ctypedef union snd_seq_timestamp_t:
        snd_seq_tick_time_t tick
        snd_seq_real_time_t time
    ctypedef struct snd_seq_ev_note_t:
        unsigned char channel
        unsigned char note
        unsigned char velocity
        unsigned char off_velocity
        unsigned int duration
    ctypedef struct snd_seq_ev_ctrl_t:
        unsigned char channel
        unsigned char unused[3]
        unsigned int param
        signed int value
    ctypedef struct snd_seq_ev_raw8_t:
        unsigned char d[12]
    ctypedef struct snd_seq_ev_raw32_t:
        unsigned int d[3]
    ctypedef packed struct snd_seq_ev_ext_t:
        unsigned int len
        void *ptr
    ctypedef struct snd_seq_result_t:
        int event
        int result
    ctypedef struct snd_seq_queue_skew_t:
        unsigned int value
        unsigned int base
    ctypedef union snd_seq_ev_queue_control_param_t:
        signed int value
        snd_seq_timestamp_t time
        unsigned int position
        snd_seq_queue_skew_t skew
        unsigned int d32[2]
        unsigned char d8[8]
    ctypedef struct snd_seq_ev_queue_control_t:
        unsigned char queue
        unsigned char unused[3]
        snd_seq_ev_queue_control_param_t param
    ctypedef union snd_seq_event_data_t:
        snd_seq_ev_note_t note
        snd_seq_ev_ctrl_t control
        snd_seq_ev_raw8_t raw8
        snd_seq_ev_raw32_t raw32
        snd_seq_ev_ext_t ext
        snd_seq_ev_queue_control_t queue
        snd_seq_timestamp_t time
        snd_seq_addr_t addr
        snd_seq_connect_t connect
        snd_seq_result_t result
    ctypedef struct snd_seq_event_t:
        snd_seq_event_type_t type
        unsigned char flags
        unsigned char tag
        unsigned char queue
        snd_seq_timestamp_t time
        snd_seq_addr_t source
        snd_seq_addr_t dest
        snd_seq_event_data_t data

    const char *snd_strerror (int errnum)

    int snd_seq_open(snd_seq_t** seq, const char* name, int streams, int mode)
    int snd_seq_close(snd_seq_t* seq)
    int snd_seq_set_client_name(snd_seq_t* seq, const char* name)
    int snd_seq_client_id(snd_seq_t* seq)
    int snd_seq_event_input_pending(snd_seq_t* seq, int fetch_sequencer)
    int snd_seq_event_input(snd_seq_t* seq, snd_seq_event_t **ev)
    int snd_seq_create_port(snd_seq_t* seq, snd_seq_port_info_t* info)
    int snd_seq_connect_from(snd_seq_t* seq, int myport, int src_client, int src_port)
    int snd_seq_disconnect_from(snd_seq_t* seq, int myport, int src_client, int src_port)

    int snd_seq_poll_descriptors_count(snd_seq_t* seq, short events)
    int snd_seq_poll_descriptors(
        snd_seq_t* seq, pollfd* pfds, unsigned int space, short events)

    int snd_seq_client_info_malloc(snd_seq_client_info_t** info)
    void snd_seq_client_info_free(snd_seq_client_info_t* info)
    void snd_seq_client_info_set_client(snd_seq_client_info_t* info, int client)
    int snd_seq_query_next_client(snd_seq_t* seq, snd_seq_client_info_t* info)
    const char* snd_seq_client_info_get_name(snd_seq_client_info_t* info)
    int snd_seq_client_info_get_client(const snd_seq_client_info_t* info)

    int snd_seq_port_info_malloc(snd_seq_port_info_t** ptr)
    void snd_seq_port_info_free(snd_seq_port_info_t* ptr)
    void snd_seq_port_info_set_client (snd_seq_port_info_t* info, int client)
    void snd_seq_port_info_set_port(snd_seq_port_info_t* info, int port)
    int snd_seq_query_next_port(snd_seq_t* seq, snd_seq_port_info_t* info)
    int snd_seq_port_info_get_port (const snd_seq_port_info_t* info)
    const char* snd_seq_port_info_get_name(const snd_seq_port_info_t* info)
    void snd_seq_port_info_set_name(snd_seq_port_info_t* info, const char* name)
    unsigned int snd_seq_port_info_get_capability(const snd_seq_port_info_t* info)
    void snd_seq_port_info_set_capability(snd_seq_port_info_t* info, unsigned int capability)
    unsigned int snd_seq_port_info_get_type(const snd_seq_port_info_t* info)
    void snd_seq_port_info_set_type(snd_seq_port_info_t* info, unsigned int type)

SND_SEQ_CLIENT_SYSTEM = 0
SND_SEQ_PORT_SYSTEM_TIMER = 0
SND_SEQ_PORT_SYSTEM_ANNOUNCE = 1

SND_SEQ_OPEN_OUTPUT = 1
SND_SEQ_OPEN_INPUT = 2
SND_SEQ_OPEN_DUPLEX = (SND_SEQ_OPEN_OUTPUT|SND_SEQ_OPEN_INPUT)

SND_SEQ_NONBLOCK = 0x0001

SND_SEQ_PORT_CAP_READ       = (1<<0)
SND_SEQ_PORT_CAP_WRITE      = (1<<1)
SND_SEQ_PORT_CAP_SYNC_READ  = (1<<2)
SND_SEQ_PORT_CAP_SYNC_WRITE = (1<<3)
SND_SEQ_PORT_CAP_DUPLEX     = (1<<4)
SND_SEQ_PORT_CAP_SUBS_READ  = (1<<5)
SND_SEQ_PORT_CAP_SUBS_WRITE = (1<<6)
SND_SEQ_PORT_CAP_NO_EXPORT  = (1<<7)

PORT_CAP_MAP = {
    SND_SEQ_PORT_CAP_READ: 'read',
    SND_SEQ_PORT_CAP_WRITE: 'write',
    SND_SEQ_PORT_CAP_SYNC_READ: 'sync_read',
    SND_SEQ_PORT_CAP_SYNC_WRITE: 'sync_write',
    SND_SEQ_PORT_CAP_DUPLEX: 'duplex',
    SND_SEQ_PORT_CAP_SUBS_READ: 'subs_read',
    SND_SEQ_PORT_CAP_SUBS_WRITE: 'subs_write',
    SND_SEQ_PORT_CAP_NO_EXPORT: 'no_export',
}

def get_port_caps(unsigned int caps):
    names = set()
    for bit, name in PORT_CAP_MAP.items():
        if caps & bit:
            names.add(name)
    return names

SND_SEQ_PORT_TYPE_SPECIFIC      = (1<<0)
SND_SEQ_PORT_TYPE_MIDI_GENERIC  = (1<<1)
SND_SEQ_PORT_TYPE_MIDI_GM       = (1<<2)
SND_SEQ_PORT_TYPE_MIDI_GS       = (1<<3)
SND_SEQ_PORT_TYPE_MIDI_XG       = (1<<4)
SND_SEQ_PORT_TYPE_MIDI_MT32     = (1<<5)
SND_SEQ_PORT_TYPE_MIDI_GM2      = (1<<6)
SND_SEQ_PORT_TYPE_SYNTH         = (1<<10)
SND_SEQ_PORT_TYPE_DIRECT_SAMPLE = (1<<11)
SND_SEQ_PORT_TYPE_SAMPLE        = (1<<12)
SND_SEQ_PORT_TYPE_HARDWARE      = (1<<16)
SND_SEQ_PORT_TYPE_SOFTWARE      = (1<<17)
SND_SEQ_PORT_TYPE_SYNTHESIZER   = (1<<18)
SND_SEQ_PORT_TYPE_PORT          = (1<<19)
SND_SEQ_PORT_TYPE_APPLICATION   = (1<<20)

PORT_TYPE_MAP = {
    SND_SEQ_PORT_TYPE_SPECIFIC: 'specific',
    SND_SEQ_PORT_TYPE_MIDI_GENERIC: 'midi_generic',
    SND_SEQ_PORT_TYPE_MIDI_GM: 'midi_gm',
    SND_SEQ_PORT_TYPE_MIDI_GS: 'midi_gs',
    SND_SEQ_PORT_TYPE_MIDI_XG: 'midi_xg',
    SND_SEQ_PORT_TYPE_MIDI_MT32: 'midi_mt32',
    SND_SEQ_PORT_TYPE_MIDI_GM2: 'midi_gm2',
    SND_SEQ_PORT_TYPE_SYNTH: 'synth',
    SND_SEQ_PORT_TYPE_DIRECT_SAMPLE: 'direct_sample',
    SND_SEQ_PORT_TYPE_SAMPLE: 'sample',
    SND_SEQ_PORT_TYPE_HARDWARE: 'hardware',
    SND_SEQ_PORT_TYPE_SOFTWARE: 'software',
    SND_SEQ_PORT_TYPE_SYNTHESIZER: 'synthesizer',
    SND_SEQ_PORT_TYPE_PORT: 'port',
    SND_SEQ_PORT_TYPE_APPLICATION: 'application',
}

def get_port_types(unsigned int types):
    names = set()
    for bit, name in PORT_TYPE_MAP.items():
        if types & bit:
            names.add(name)
    return names

cdef enum:
    SND_SEQ_EVENT_SYSTEM = 0,
    SND_SEQ_EVENT_RESULT,
    SND_SEQ_EVENT_NOTE = 5,
    SND_SEQ_EVENT_NOTEON,
    SND_SEQ_EVENT_NOTEOFF,
    SND_SEQ_EVENT_KEYPRESS,
    SND_SEQ_EVENT_CONTROLLER = 10,
    SND_SEQ_EVENT_PGMCHANGE,
    SND_SEQ_EVENT_CHANPRESS,
    SND_SEQ_EVENT_PITCHBEND,
    SND_SEQ_EVENT_CONTROL14,
    SND_SEQ_EVENT_NONREGPARAM,
    SND_SEQ_EVENT_REGPARAM,
    SND_SEQ_EVENT_SONGPOS = 20,
    SND_SEQ_EVENT_SONGSEL,
    SND_SEQ_EVENT_QFRAME,
    SND_SEQ_EVENT_TIMESIGN,
    SND_SEQ_EVENT_KEYSIGN,
    SND_SEQ_EVENT_START = 30,
    SND_SEQ_EVENT_CONTINUE,
    SND_SEQ_EVENT_STOP,
    SND_SEQ_EVENT_SETPOS_TICK,
    SND_SEQ_EVENT_SETPOS_TIME,
    SND_SEQ_EVENT_TEMPO,
    SND_SEQ_EVENT_CLOCK,
    SND_SEQ_EVENT_TICK,
    SND_SEQ_EVENT_QUEUE_SKEW,
    SND_SEQ_EVENT_SYNC_POS,
    SND_SEQ_EVENT_TUNE_REQUEST = 40,
    SND_SEQ_EVENT_RESET,
    SND_SEQ_EVENT_SENSING,
    SND_SEQ_EVENT_ECHO = 50,
    SND_SEQ_EVENT_OSS,
    SND_SEQ_EVENT_CLIENT_START = 60,
    SND_SEQ_EVENT_CLIENT_EXIT,
    SND_SEQ_EVENT_CLIENT_CHANGE,
    SND_SEQ_EVENT_PORT_START,
    SND_SEQ_EVENT_PORT_EXIT,
    SND_SEQ_EVENT_PORT_CHANGE,
    SND_SEQ_EVENT_PORT_SUBSCRIBED,
    SND_SEQ_EVENT_PORT_UNSUBSCRIBED,
    SND_SEQ_EVENT_USR0 = 90,
    SND_SEQ_EVENT_USR1,
    SND_SEQ_EVENT_USR2,
    SND_SEQ_EVENT_USR3,
    SND_SEQ_EVENT_USR4,
    SND_SEQ_EVENT_USR5,
    SND_SEQ_EVENT_USR6,
    SND_SEQ_EVENT_USR7,
    SND_SEQ_EVENT_USR8,
    SND_SEQ_EVENT_USR9,
    SND_SEQ_EVENT_SYSEX = 130,
    SND_SEQ_EVENT_BOUNCE,
    SND_SEQ_EVENT_USR_VAR0 = 135,
    SND_SEQ_EVENT_USR_VAR1,
    SND_SEQ_EVENT_USR_VAR2,
    SND_SEQ_EVENT_USR_VAR3,
    SND_SEQ_EVENT_USR_VAR4,
    SND_SEQ_EVENT_NONE = 255

SND_SEQ_TIME_STAMP_TICK = (0<<0)
SND_SEQ_TIME_STAMP_REAL = (1<<0)
SND_SEQ_TIME_STAMP_MASK = (1<<0)

class Error(Exception):
    pass

class APIError(Error):
    def __init__(self, errno):
        super().__init__(bytes(snd_strerror(errno)).decode('utf-8'))
        self.errno = errno


def CHECK(errno):
    if errno < 0:
        raise APIError(errno)


class ClientInfo(object):
    def __init__(self, client_id, name):
        self.client_id = client_id
        self.name = name

    def __str__(self):
        return '<ClientInfo "%s" id=%d>' % (self.name, self.client_id)


class PortInfo(object):
    def __init__(self, client_info, port_id, name, capabilities, types):
        self.client_info = client_info
        self.port_id = port_id
        self.name = name
        self.capabilities = capabilities
        self.types = types

    def __str__(self):
        return '<PortInfo "%s" client="%s" id=%d caps=%s types=%s>' % (
            self.name, self.client_info.name, self.port_id,
            ','.join(self.capabilities), ','.join(self.types))

    @property
    def device_id(self):
        return '%d/%d' % (self.client_info.client_id, self.port_id)


cdef class AlsaSequencer(object):
    cdef str name
    cdef snd_seq_t* seq
    cdef int client_id
    cdef int input_port_id

    def __cinit__(self):
        self.seq = NULL

    def __init__(self, name="seq"):
        self.name = name

        CHECK(snd_seq_open(
            &self.seq, "default", SND_SEQ_OPEN_DUPLEX, SND_SEQ_NONBLOCK))
        CHECK(snd_seq_set_client_name(self.seq, self.name.encode('utf-8')))
        self.client_id = snd_seq_client_id(self.seq)

        # Create an input port.
        cdef snd_seq_port_info_t *pinfo
        CHECK(snd_seq_port_info_malloc(&pinfo))
        try:
            snd_seq_port_info_set_capability(pinfo, SND_SEQ_PORT_CAP_WRITE)
            snd_seq_port_info_set_type(
                pinfo,
                SND_SEQ_PORT_TYPE_MIDI_GENERIC | SND_SEQ_PORT_TYPE_APPLICATION)
            snd_seq_port_info_set_name(pinfo, "Input")
            CHECK(snd_seq_create_port(self.seq, pinfo))
            self.input_port_id = snd_seq_port_info_get_port(pinfo)

        finally:
            snd_seq_port_info_free(pinfo)

        # Connect to System Announce port
        CHECK(snd_seq_connect_from(
            self.seq, self.input_port_id,
            SND_SEQ_CLIENT_SYSTEM, SND_SEQ_PORT_SYSTEM_ANNOUNCE))

    def __dealloc__(self):
        if self.seq != NULL:
            self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _check_open(self):
        if self.seq == NULL:
            raise Error("Not opened")

    def close(self):
        self._check_open()
        CHECK(snd_seq_close(self.seq))
        self.seq = NULL

    def list_clients(self):
        self._check_open()

        cdef snd_seq_client_info_t *cinfo
        cdef int client_id

        CHECK(snd_seq_client_info_malloc(&cinfo))
        try:
            snd_seq_client_info_set_client(cinfo, -1)
            while snd_seq_query_next_client(self.seq, cinfo) == 0:
                client_id = snd_seq_client_info_get_client(cinfo)
                if client_id == self.client_id:
                    # Ignore me, myself and I
                    continue
                client_name = (
                    bytes(snd_seq_client_info_get_name(cinfo)).decode('utf-8'))
                yield ClientInfo(client_id, client_name)

        finally:
            snd_seq_client_info_free(cinfo)

    def list_client_ports(self, client_info):
        self._check_open()

        cdef snd_seq_port_info_t *pinfo

        CHECK(snd_seq_port_info_malloc(&pinfo))
        try:
            snd_seq_port_info_set_client(pinfo, client_info.client_id)
            snd_seq_port_info_set_port(pinfo, -1)
            while snd_seq_query_next_port(self.seq, pinfo) == 0:
                port_id = snd_seq_port_info_get_port(pinfo)
                port_name = (
                    bytes(snd_seq_port_info_get_name(pinfo)).decode('utf-8'))
                caps = get_port_caps(snd_seq_port_info_get_capability(pinfo))
                types = get_port_types(snd_seq_port_info_get_type(pinfo))
                yield PortInfo(client_info, port_id, port_name, caps, types)

        finally:
            snd_seq_port_info_free(pinfo)

    def list_all_ports(self):
        for client_info in self.list_clients():
            for port_info in self.list_client_ports(client_info):
                yield port_info

    def connect(self, port_info):
        self._check_open()

        CHECK(snd_seq_connect_from(
            self.seq, self.input_port_id,
            port_info.client_info.client_id, port_info.port_id))

    def disconnect(self, port_info):
        self._check_open()

        CHECK(snd_seq_disconnect_from(
            self.seq, self.input_port_id,
            port_info.client_info.client_id, port_info.port_id))

    def get_pollin_fds(self):
        cdef int numfds = snd_seq_poll_descriptors_count(self.seq, POLLIN)
        assert numfds < 10
        cdef pollfd pollfds[10]
        numfds = snd_seq_poll_descriptors(self.seq, pollfds, 10, POLLIN)
        return [pollfds[i].fd for i in range(numfds)]

    def get_event(self):
        cdef snd_seq_event_t* event
        result = snd_seq_event_input(self.seq, &event)
        if result == -errno.EAGAIN:
            return None
        CHECK(result)

        assert event.flags & SND_SEQ_TIME_STAMP_MASK == SND_SEQ_TIME_STAMP_TICK
        timestamp = event.time.tick
        device_id = '%d/%d' % (event.source.client, event.source.port)

        if event.type == SND_SEQ_EVENT_NOTEON:
            return midi_events.NoteOnEvent(
                timestamp, device_id,
                event.data.note.channel,
                event.data.note.note,
                event.data.note.velocity)

        elif event.type == SND_SEQ_EVENT_NOTEOFF:
            return midi_events.NoteOffEvent(
                timestamp, device_id,
                event.data.note.channel,
                event.data.note.note,
                event.data.note.velocity)

        elif event.type == SND_SEQ_EVENT_CONTROLLER:
            return midi_events.ControlChangeEvent(
                timestamp, device_id,
                event.data.note.channel,
                event.data.control.param,
                event.data.control.value)

        elif event.type in (SND_SEQ_EVENT_CLIENT_START,
                            SND_SEQ_EVENT_CLIENT_CHANGE,
                            SND_SEQ_EVENT_CLIENT_EXIT,
                            SND_SEQ_EVENT_PORT_START,
                            SND_SEQ_EVENT_PORT_CHANGE,
                            SND_SEQ_EVENT_PORT_EXIT):
            return midi_events.DeviceChangeEvent(
                timestamp, device_id,
                {SND_SEQ_EVENT_CLIENT_START: 'client-start',
                 SND_SEQ_EVENT_CLIENT_CHANGE: 'client-change',
                 SND_SEQ_EVENT_CLIENT_EXIT: 'client-exit',
                 SND_SEQ_EVENT_PORT_START: 'port-start',
                 SND_SEQ_EVENT_PORT_CHANGE: 'port-change',
                 SND_SEQ_EVENT_PORT_EXIT: 'port-exit',
                }[event.type],
                event.data.addr.client, event.data.addr.port)

        elif event.type in (SND_SEQ_EVENT_PORT_SUBSCRIBED,
                            SND_SEQ_EVENT_PORT_UNSUBSCRIBED):
            # Ignore these events.
            return None

        logger.error("Unknown event type: 0x%02x" % event.type)
        return None
