import logging
import os

__version__ = bytes(fluid_version_str()).decode('ascii')

def version():
    cdef int major, minor, micro
    fluid_version(&major, &minor, &micro)
    return (int(major), int(minor), int(micro))


__log_level_map = {
    FLUID_PANIC: logging.CRITICAL,
    FLUID_ERR: logging.ERROR,
    FLUID_WARN: logging.WARNING,
    FLUID_INFO: logging.INFO,
    FLUID_DBG: logging.DEBUG,
}

logger = logging.getLogger(__name__)

cdef void __log_cb(int level, char* message, void* data) nogil:
    with gil:
        logger.log(__log_level_map[level], message.decode('utf-8'))

fluid_set_log_function(FLUID_PANIC, __log_cb, NULL)
fluid_set_log_function(FLUID_ERR, __log_cb, NULL)
fluid_set_log_function(FLUID_WARN, __log_cb, NULL)
fluid_set_log_function(FLUID_INFO, __log_cb, NULL)
fluid_set_log_function(FLUID_DBG, __log_cb, NULL)



class Error(Exception):
    pass


cdef class Settings(object):
    def __init__(self):
        self.handle = new_fluid_settings()
        if self.handle == NULL:
            raise MemoryError

    def __dealloc__(self):
        if self.handle != NULL:
            delete_fluid_settings(self.handle)
            self.handle = NULL

    @property
    def synth_gain(self):
        cdef double val
        cdef int ok = fluid_settings_getnum(self.handle, 'synth.gain', &val)
        if not ok:
            raise ValueError("Failed to get synth.gain")
        return float(val)

    @synth_gain.setter
    def synth_gain(self, double val):
        cdef int ok = fluid_settings_setnum(self.handle, 'synth.gain', val)
        if not ok:
            raise ValueError("Failed to set synth.gain=%s" % val)

    @property
    def synth_sample_rate(self):
        cdef double val
        cdef int ok = fluid_settings_getnum(self.handle, 'synth.sample-rate', &val)
        if not ok:
            raise ValueError("Failed to get synth.sample-rate")
        return float(val)

    @synth_sample_rate.setter
    def synth_sample_rate(self, double val):
        cdef int ok = fluid_settings_setnum(self.handle, 'synth.sample-rate', val)
        if not ok:
            raise ValueError("Failed to set synth.sample-rate=%s" % val)

    @property
    def synth_midi_channels(self):
        cdef int val
        cdef int ok = fluid_settings_getint(self.handle, 'synth.midi-channels', &val)
        if not ok:
            raise ValueError("Failed to get synth.midi-channels")
        return float(val)

    @synth_midi_channels.setter
    def synth_midi_channels(self, int val):
        cdef int ok = fluid_settings_setint(self.handle, 'synth.midi-channels', val)
        if not ok:
            raise ValueError("Failed to set synth.midi-channels=%s" % val)

    @property
    def synth_audio_channels(self):
        cdef int val
        cdef int ok = fluid_settings_getint(self.handle, 'synth.audio-channels', &val)
        if not ok:
            raise ValueError("Failed to get synth.audio-channels")
        return val

    @synth_audio_channels.setter
    def synth_audio_channels(self, int val):
        cdef int ok = fluid_settings_setint(self.handle, 'synth.audio-channels', val)
        if not ok:
            raise ValueError("Failed to set synth.audio-channels=%s" % val)


cdef class Soundfont(object):
    def __cinit__(self):
        self.handle = NULL

    def __dealloc__(self):
        self.handle = NULL

    cdef init(self, fluid_sfont_t* handle):
        assert self.handle == NULL
        self.handle = handle
        return self

    @property
    def id(self):
        return int(self.handle.id)


cdef class Synth(object):
    def __cinit__(self):
        self.handle = NULL
        self.settings = None

    def __init__(self, Settings settings=None):
        if settings is None:
            settings = Settings()
        self.settings = settings
        self.handle = new_fluid_synth(settings.handle)

    def __dealloc__(self):
        if self.handle != NULL:
            delete_fluid_synth(self.handle)
            self.handle = NULL

    cdef int __check_failed(self, int status) nogil except -1:
        if status == FLUID_FAILED:
            with gil:
                raise Error(fluid_synth_error(self.handle).decode('ascii'))
        return 0

    def sfload(self, str path, int reset_presets=0):
        pathb = os.fsencode(path)
        cdef int sf_id = fluid_synth_sfload(self.handle, pathb, reset_presets)
        self.__check_failed(sf_id)
        return int(sf_id)

    def get_sfont(self, int sf_id):
        cdef fluid_sfont_t* sfont
        sfont = fluid_synth_get_sfont_by_id(self.handle, sf_id)
        if sfont == NULL:
            raise Error("Soundfont %d does not exist" % sf_id)
        return Soundfont().init(sfont)

    def add_sfont(self, Soundfont sfont):
        cdef int sf_id = fluid_synth_add_sfont(self.handle, sfont.handle)
        self.__check_failed(sf_id)
        return int(sf_id)

    def remove_sfont(self, Soundfont sfont):
        fluid_synth_remove_sfont(self.handle, sfont.handle)

    def system_reset(self):
        self.__check_failed(
            fluid_synth_system_reset(self.handle))

    def program_select(self, int channel, int sf_id, int bank, int preset):
        self.__check_failed(
            fluid_synth_program_select(self.handle, channel, sf_id, bank, preset))

    cdef int noteon(self, int channel, int key, int vel) nogil except -1:
        self.__check_failed(
            fluid_synth_noteon(self.handle, channel, key, vel))
        return 0

    cdef void noteoff(self, int channel, int key) nogil:
        fluid_synth_noteoff(self.handle, channel, key)

    def get_samples(self, int num_samples):
        left = bytearray(4 * num_samples)
        right = bytearray(4 * num_samples)
        self.get_samples_into(num_samples, <float*><char*>left, <float*><char*>right)
        return left, right

    cdef int get_samples_into(
        self, int num_samples, float* left, float* right) nogil except -1:
        cdef float* lmap[1]
        cdef float* rmap[1]
        lmap[0] = left
        rmap[0] = right
        self.__check_failed(
            fluid_synth_nwrite_float(self.handle, num_samples, lmap, rmap, NULL, NULL))
        return 0
