import logging
import os


### DECLARATIONS ##########################################################

cdef extern from "fluidsynth.h":
    ## fluidsynth/types.h - Type declarations

    ctypedef void fluid_settings_t
    ctypedef void fluid_synth_t
    ctypedef _fluid_sfont_t fluid_sfont_t
    ctypedef void fluid_preset_t


    ## fluidsynth/settings.h - Synthesizer settings

    fluid_settings_t* new_fluid_settings()
    void delete_fluid_settings(fluid_settings_t* settings)

    int fluid_settings_setnum(fluid_settings_t* settings, const char *name, double val)
    int fluid_settings_getnum(fluid_settings_t* settings, const char *name, double* val)

    int fluid_settings_setint(fluid_settings_t* settings, const char *name, int val)
    int fluid_settings_getint(fluid_settings_t* settings, const char *name, int* val)


    ## fluidsynth/version.h - Library version functions and defines

    void fluid_version(int *major, int *minor, int *micro)
    char* fluid_version_str()


    ## fluidsynth/synth.h - Embeddable SoundFont synthesizer

    fluid_synth_t* new_fluid_synth(fluid_settings_t* settings)
    int delete_fluid_synth(fluid_synth_t* synth)
    int fluid_synth_noteon(fluid_synth_t* synth, int chan, int key, int vel)
    int fluid_synth_noteoff(fluid_synth_t* synth, int chan, int key)
    int fluid_synth_program_select(fluid_synth_t* synth, int chan, unsigned int sfont_id,
                                   unsigned int bank_num, unsigned int preset_num)
    int fluid_synth_system_reset(fluid_synth_t* synth)
    int fluid_synth_sfload(fluid_synth_t* synth, const char* filename, int reset_presets);
    int fluid_synth_add_sfont(fluid_synth_t* synth, fluid_sfont_t* sfont)
    void fluid_synth_remove_sfont(fluid_synth_t* synth, fluid_sfont_t* sfont)
    fluid_sfont_t* fluid_synth_get_sfont_by_id(fluid_synth_t* synth, unsigned int id)
    char* fluid_synth_error(fluid_synth_t* synth)
    int fluid_synth_nwrite_float(fluid_synth_t* synth, int len,
                                 float** left, float** right,
                                 float** fx_left, float** fx_right)


    ## fluidsynth/misc.h - Miscellaneous utility functions and defines

    cdef enum:
        FLUID_OK = 0
        FLUID_FAILED = -1


    ## fluisynth/sfont.h - SoundFont plugins

    cdef struct _fluid_sfont_t:
        void* data
        unsigned int id
        int (*free)(fluid_sfont_t* sfont);
        char* (*get_name)(fluid_sfont_t* sfont);
        fluid_preset_t* (*get_preset)(fluid_sfont_t* sfont, unsigned int bank, unsigned int prenum);
        void (*iteration_start)(fluid_sfont_t* sfont);
        int (*iteration_next)(fluid_sfont_t* sfont, fluid_preset_t* preset);


    ## fluidsynth/log.h - Logging interface

    cdef enum fluid_log_level:
        FLUID_PANIC
        FLUID_ERR
        FLUID_WARN
        FLUID_INFO
        FLUID_DBG
        LAST_LOG_LEVEL

    ctypedef void (*fluid_log_function_t)(int level, char* message, void* data)

    fluid_log_function_t fluid_set_log_function(int level, fluid_log_function_t fun, void* data)
    void fluid_default_log_function(int level, char* message, void* data)
    int fluid_log(int level, const char *fmt, ...)


### CLIENT CODE ###########################################################

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

cdef void __log_cb(int level, char* message, void* data):
    logger.log(__log_level_map[level], message.decode('utf-8'))

fluid_set_log_function(FLUID_PANIC, __log_cb, NULL)
fluid_set_log_function(FLUID_ERR, __log_cb, NULL)
fluid_set_log_function(FLUID_WARN, __log_cb, NULL)
fluid_set_log_function(FLUID_INFO, __log_cb, NULL)
fluid_set_log_function(FLUID_DBG, __log_cb, NULL)



class Error(Exception):
    pass


cdef class Settings(object):
    cdef fluid_settings_t* handle

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
        return float(val)

    @synth_audio_channels.setter
    def synth_audio_channels(self, int val):
        cdef int ok = fluid_settings_setint(self.handle, 'synth.audio-channels', val)
        if not ok:
            raise ValueError("Failed to set synth.audio-channels=%s" % val)


cdef class Soundfont(object):
    cdef fluid_sfont_t* handle

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
    cdef fluid_synth_t* handle
    cdef readonly Settings settings

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

    cdef __check_failed(self, int status):
        if status == FLUID_FAILED:
            raise Error(fluid_synth_error(self.handle).decode('ascii'))

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

    def noteon(self, int channel, int key, int vel):
        self.__check_failed(
            fluid_synth_noteon(self.handle, channel, key, vel))

    def noteoff(self, int channel, int key):
        fluid_synth_noteoff(self.handle, channel, key)

    def get_samples(self, int num_samples):
        assert self.settings.synth_audio_channels == 1
        leftb = bytearray(4 * num_samples)
        rightb = bytearray(4 * num_samples)
        cdef float* left[1]
        cdef float* right[1]
        left[0] = <float*><char*>leftb
        right[0] = <float*><char*>rightb
        self.__check_failed(
            fluid_synth_nwrite_float(self.handle, num_samples, left, right, NULL, NULL))
        return leftb, rightb
