
cdef extern from "fluidsynth.h" nogil:
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


cdef class Settings(object):
    cdef fluid_settings_t* handle


cdef class Soundfont(object):
    cdef fluid_sfont_t* handle

    cdef init(self, fluid_sfont_t* handle)


cdef class Synth(object):
    cdef fluid_synth_t* handle
    cdef readonly Settings settings

    cdef int __check_failed(self, int status) nogil except -1
    cdef int noteon(self, int channel, int key, int vel) nogil except -1
    cdef void noteoff(self, int channel, int key) nogil
    cdef int get_samples_into(self, int num_samples, float* left, float* right) nogil except -1
