# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

from libc.stdint cimport int64_t
from libc.stdio cimport SEEK_SET
import enum
import numpy
cimport numpy

### DECLARATIONS ##########################################################

cdef extern from "sndfile.h":
    cdef enum:
        # Major formats.
        SF_FORMAT_WAV
        SF_FORMAT_AIFF
        SF_FORMAT_AU
        SF_FORMAT_RAW
        SF_FORMAT_PAF
        SF_FORMAT_SVX
        SF_FORMAT_NIST
        SF_FORMAT_VOC
        SF_FORMAT_IRCAM
        SF_FORMAT_W64
        SF_FORMAT_MAT4
        SF_FORMAT_MAT5
        SF_FORMAT_PVF
        SF_FORMAT_XI
        SF_FORMAT_HTK
        SF_FORMAT_SDS
        SF_FORMAT_AVR
        SF_FORMAT_WAVEX
        SF_FORMAT_SD2
        SF_FORMAT_FLAC
        SF_FORMAT_CAF
        SF_FORMAT_WVE
        SF_FORMAT_OGG
        SF_FORMAT_MPC2K
        SF_FORMAT_RF64

	# Subtypes from here on.
        SF_FORMAT_PCM_S8
        SF_FORMAT_PCM_16
        SF_FORMAT_PCM_24
        SF_FORMAT_PCM_32
        SF_FORMAT_PCM_U8
        SF_FORMAT_FLOAT
        SF_FORMAT_DOUBLE
        SF_FORMAT_ULAW
        SF_FORMAT_ALAW
        SF_FORMAT_IMA_ADPCM
        SF_FORMAT_MS_ADPCM
        SF_FORMAT_GSM610
        SF_FORMAT_VOX_ADPCM
        SF_FORMAT_G721_32
        SF_FORMAT_G723_24
        SF_FORMAT_G723_40
        SF_FORMAT_DWVW_12
        SF_FORMAT_DWVW_16
        SF_FORMAT_DWVW_24
        SF_FORMAT_DWVW_N
        SF_FORMAT_DPCM_8
        SF_FORMAT_DPCM_16
        SF_FORMAT_VORBIS

	# Endian-ness options.
        SF_ENDIAN_FILE
        SF_ENDIAN_LITTLE
        SF_ENDIAN_BIG
        SF_ENDIAN_CPU

        SF_FORMAT_SUBMASK
        SF_FORMAT_TYPEMASK
        SF_FORMAT_ENDMASK

    cdef enum:
        SFC_GET_LIB_VERSION
        SFC_GET_LOG_INFO
        SFC_GET_CURRENT_SF_INFO
        SFC_GET_NORM_DOUBLE
        SFC_GET_NORM_FLOAT
        SFC_SET_NORM_DOUBLE
        SFC_SET_NORM_FLOAT
        SFC_SET_SCALE_FLOAT_INT_READ
        SFC_SET_SCALE_INT_FLOAT_WRITE
        SFC_GET_SIMPLE_FORMAT_COUNT
        SFC_GET_SIMPLE_FORMAT
        SFC_GET_FORMAT_INFO
        SFC_GET_FORMAT_MAJOR_COUNT
        SFC_GET_FORMAT_MAJOR
        SFC_GET_FORMAT_SUBTYPE_COUNT
        SFC_GET_FORMAT_SUBTYPE
        SFC_CALC_SIGNAL_MAX
        SFC_CALC_NORM_SIGNAL_MAX
        SFC_CALC_MAX_ALL_CHANNELS
        SFC_CALC_NORM_MAX_ALL_CHANNELS
        SFC_GET_SIGNAL_MAX
        SFC_GET_MAX_ALL_CHANNELS
        SFC_SET_ADD_PEAK_CHUNK
        SFC_SET_ADD_HEADER_PAD_CHUNK
        SFC_UPDATE_HEADER_NOW
        SFC_SET_UPDATE_HEADER_AUTO
        SFC_FILE_TRUNCATE
        SFC_SET_RAW_START_OFFSET
        SFC_SET_DITHER_ON_WRITE
        SFC_SET_DITHER_ON_READ
        SFC_GET_DITHER_INFO_COUNT
        SFC_GET_DITHER_INFO
        SFC_GET_EMBED_FILE_INFO
        SFC_SET_CLIPPING
        SFC_GET_CLIPPING
        SFC_GET_INSTRUMENT
        SFC_SET_INSTRUMENT
        SFC_GET_LOOP_INFO
        SFC_GET_BROADCAST_INFO
        SFC_SET_BROADCAST_INFO
        SFC_GET_CHANNEL_MAP_INFO
        SFC_SET_CHANNEL_MAP_INFO
        SFC_RAW_DATA_NEEDS_ENDSWAP
        SFC_WAVEX_SET_AMBISONIC
        SFC_WAVEX_GET_AMBISONIC
        SFC_SET_VBR_ENCODING_QUALITY
        SFC_TEST_IEEE_FLOAT_REPLACE
        SFC_SET_ADD_DITHER_ON_WRITE
        SFC_SET_ADD_DITHER_ON_READ

    cdef enum:
        SF_STR_TITLE
        SF_STR_COPYRIGHT
        SF_STR_SOFTWARE
        SF_STR_ARTIST
        SF_STR_COMMENT
        SF_STR_DATE
        SF_STR_ALBUM
        SF_STR_LICENSE
        SF_STR_TRACKNUMBER
        SF_STR_GENRE

    cdef enum:
        SF_FALSE
        SF_TRUE
        SFM_READ
        SFM_WRITE
        SFM_RDWR
        SF_AMBISONIC_NONE
        SF_AMBISONIC_B_FORMAT

    cdef enum:
        SF_ERR_NO_ERROR
        SF_ERR_UNRECOGNISED_FORMAT
        SF_ERR_SYSTEM
        SF_ERR_MALFORMED_FILE
        SF_ERR_UNSUPPORTED_ENCODING

    cdef enum:
        SF_CHANNEL_MAP_INVALID
        SF_CHANNEL_MAP_MONO
        SF_CHANNEL_MAP_LEFT
        SF_CHANNEL_MAP_RIGHT
        SF_CHANNEL_MAP_CENTER
        SF_CHANNEL_MAP_FRONT_LEFT
        SF_CHANNEL_MAP_FRONT_RIGHT
        SF_CHANNEL_MAP_FRONT_CENTER
        SF_CHANNEL_MAP_REAR_CENTER
        SF_CHANNEL_MAP_REAR_LEFT
        SF_CHANNEL_MAP_REAR_RIGHT
        SF_CHANNEL_MAP_LFE
        SF_CHANNEL_MAP_FRONT_LEFT_OF_CENTER
        SF_CHANNEL_MAP_FRONT_RIGHT_OF_CENTER
        SF_CHANNEL_MAP_SIDE_LEFT
        SF_CHANNEL_MAP_SIDE_RIGHT
        SF_CHANNEL_MAP_TOP_CENTER
        SF_CHANNEL_MAP_TOP_FRONT_LEFT
        SF_CHANNEL_MAP_TOP_FRONT_RIGHT
        SF_CHANNEL_MAP_TOP_FRONT_CENTER
        SF_CHANNEL_MAP_TOP_REAR_LEFT
        SF_CHANNEL_MAP_TOP_REAR_RIGHT
        SF_CHANNEL_MAP_TOP_REAR_CENTER
        SF_CHANNEL_MAP_AMBISONIC_B_W
        SF_CHANNEL_MAP_AMBISONIC_B_X
        SF_CHANNEL_MAP_AMBISONIC_B_Y
        SF_CHANNEL_MAP_AMBISONIC_B_Z
        SF_CHANNEL_MAP_MAX

    ctypedef void SNDFILE

    ctypedef int64_t sf_count_t

    cdef struct SF_INFO:
        sf_count_t frames
        int samplerate
        int channels
        int format
        int sections
        int seekable

    ctypedef SF_INFO SF_INFO

    cdef struct _SF_FORMAT_INFO_s:
        int format
        char* name
        char* extension

    ctypedef _SF_FORMAT_INFO_s SF_FORMAT_INFO

    cdef enum:
        SFD_DEFAULT_LEVEL
        SFD_CUSTOM_LEVEL
        SFD_NO_DITHER
        SFD_WHITE
        SFD_TRIANGULAR_PDF

    cdef struct _SF_DITHER_INFO_s:
        int type
        double level
        char* name

    ctypedef _SF_DITHER_INFO_s SF_DITHER_INFO

    cdef struct _SF_EMBED_FILE_INFO_s:
        sf_count_t offset
        sf_count_t length

    ctypedef _SF_EMBED_FILE_INFO_s SF_EMBED_FILE_INFO

    cdef enum:
        SF_LOOP_NONE
        SF_LOOP_FORWARD
        SF_LOOP_BACKWARD
        SF_LOOP_ALTERNATING

    cdef struct _SF_INSTRUMENT_SF_INSTRUMENT_loops_s:
        int mode
        unsigned int start
        unsigned int end
        unsigned int count

    cdef struct _SF_INSTRUMENT_s:
        int gain
        char basenote
        char detune
        char velocity_lo
        char velocity_hi
        char key_lo
        char key_hi
        int loop_count
        _SF_INSTRUMENT_SF_INSTRUMENT_loops_s loops[1]

    ctypedef _SF_INSTRUMENT_s SF_INSTRUMENT

    cdef struct _SF_LOOP_INFO_s:
        short time_sig_num
        short time_sig_den
        int loop_mode
        int num_beats
        float bpm
        int root_key
        int future[1]

    ctypedef _SF_LOOP_INFO_s SF_LOOP_INFO

    cdef struct _SF_BROADCAST_INFO_s:
        char description[1]
        char originator[1]
        char originator_reference[1]
        char origination_date[1]
        char origination_time[1]
        unsigned int time_reference_low
        unsigned int time_reference_high
        short version
        char umid[1]
        char reserved[1]
        unsigned int coding_history_size
        char coding_history[1]

    ctypedef _SF_BROADCAST_INFO_s SF_BROADCAST_INFO

    ctypedef sf_count_t (*sf_vio_get_filelen)(void* user_data)

    ctypedef sf_count_t (*sf_vio_seek)(sf_count_t offset, int whence, void* user_data)

    ctypedef sf_count_t (*sf_vio_read)(void* ptr, sf_count_t count, void* user_data)

    ctypedef sf_count_t (*sf_vio_write)(void* ptr, sf_count_t count, void* user_data)

    ctypedef sf_count_t (*sf_vio_tell)(void* user_data)

    cdef struct SF_VIRTUAL_IO:
        sf_vio_get_filelen get_filelen
        sf_vio_seek seek
        sf_vio_read read
        sf_vio_write write
        sf_vio_tell tell

    ctypedef SF_VIRTUAL_IO SF_VIRTUAL_IO

    SNDFILE* sf_open(char* path, int mode, SF_INFO* sfinfo)

    SNDFILE* sf_open_fd(int fd, int mode, SF_INFO* sfinfo, int close_desc)

    SNDFILE* sf_open_virtual(SF_VIRTUAL_IO* sfvirtual, int mode, SF_INFO* sfinfo, void* user_data)

    int sf_error(SNDFILE* sndfile)

    char* sf_strerror(SNDFILE* sndfile)

    char* sf_error_number(int errnum)

    int sf_perror(SNDFILE* sndfile)

    int sf_error_str(SNDFILE* sndfile, char* str, size_t len)

    int sf_command(SNDFILE* sndfile, int command, void* data, int datasize)

    int sf_format_check(SF_INFO* info)

    sf_count_t sf_seek(SNDFILE* sndfile, sf_count_t frames, int whence)

    int sf_set_string(SNDFILE* sndfile, int str_type, char* str)

    char* sf_get_string(SNDFILE* sndfile, int str_type)

    char* sf_version_string()

    sf_count_t sf_read_raw(SNDFILE* sndfile, void* ptr, sf_count_t bytes)

    sf_count_t sf_write_raw(SNDFILE* sndfile, void* ptr, sf_count_t bytes)

    sf_count_t sf_readf_short(SNDFILE* sndfile, short* ptr, sf_count_t frames)

    sf_count_t sf_writef_short(SNDFILE* sndfile, short* ptr, sf_count_t frames)

    sf_count_t sf_readf_int(SNDFILE* sndfile, int* ptr, sf_count_t frames)

    sf_count_t sf_writef_int(SNDFILE* sndfile, int* ptr, sf_count_t frames)

    sf_count_t sf_readf_float(SNDFILE* sndfile, float* ptr, sf_count_t frames)

    sf_count_t sf_writef_float(SNDFILE* sndfile, float* ptr, sf_count_t frames)

    sf_count_t sf_readf_double(SNDFILE* sndfile, double* ptr, sf_count_t frames)

    sf_count_t sf_writef_double(SNDFILE* sndfile, double* ptr, sf_count_t frames)

    sf_count_t sf_read_short(SNDFILE* sndfile, short* ptr, sf_count_t items)

    sf_count_t sf_write_short(SNDFILE* sndfile, short* ptr, sf_count_t items)

    sf_count_t sf_read_int(SNDFILE* sndfile, int* ptr, sf_count_t items)

    sf_count_t sf_write_int(SNDFILE* sndfile, int* ptr, sf_count_t items)

    sf_count_t sf_read_float(SNDFILE* sndfile, float* ptr, sf_count_t items)

    sf_count_t sf_write_float(SNDFILE* sndfile, float* ptr, sf_count_t items)

    sf_count_t sf_read_double(SNDFILE* sndfile, double* ptr, sf_count_t items)

    sf_count_t sf_write_double(SNDFILE* sndfile, double* ptr, sf_count_t items)

    int sf_close(SNDFILE* sndfile)

    void sf_write_sync(SNDFILE* sndfile)


### CLIENT CODE ###########################################################

class Error(Exception):
    pass


class FileFormat(enum.Enum):
    WAV = SF_FORMAT_WAV
    AIFF = SF_FORMAT_AIFF
    AU = SF_FORMAT_AU
    RAW = SF_FORMAT_RAW
    PAF = SF_FORMAT_PAF
    SVX = SF_FORMAT_SVX
    NIST = SF_FORMAT_NIST
    VOC = SF_FORMAT_VOC
    IRCAM = SF_FORMAT_IRCAM
    W64 = SF_FORMAT_W64
    MAT4 = SF_FORMAT_MAT4
    MAT5 = SF_FORMAT_MAT5
    PVF = SF_FORMAT_PVF
    XI = SF_FORMAT_XI
    HTK = SF_FORMAT_HTK
    SDS = SF_FORMAT_SDS
    AVR = SF_FORMAT_AVR
    WAVEX = SF_FORMAT_WAVEX
    SD2 = SF_FORMAT_SD2
    FLAC = SF_FORMAT_FLAC
    CAF = SF_FORMAT_CAF
    WVE = SF_FORMAT_WVE
    OGG = SF_FORMAT_OGG
    MPC2K = SF_FORMAT_MPC2K
    RF64 = SF_FORMAT_RF64


class Encoding(enum.Enum):
    PCM_S8 = SF_FORMAT_PCM_S8
    PCM_16 = SF_FORMAT_PCM_16
    PCM_24 = SF_FORMAT_PCM_24
    PCM_32 = SF_FORMAT_PCM_32
    PCM_U8 = SF_FORMAT_PCM_U8
    FLOAT = SF_FORMAT_FLOAT
    DOUBLE = SF_FORMAT_DOUBLE
    ULAW = SF_FORMAT_ULAW
    ALAW = SF_FORMAT_ALAW
    IMA_ADPCM = SF_FORMAT_IMA_ADPCM
    MS_ADPCM = SF_FORMAT_MS_ADPCM
    GSM610 = SF_FORMAT_GSM610
    VOX_ADPCM = SF_FORMAT_VOX_ADPCM
    G721_32 = SF_FORMAT_G721_32
    G723_24 = SF_FORMAT_G723_24
    G723_40 = SF_FORMAT_G723_40
    DWVW_12 = SF_FORMAT_DWVW_12
    DWVW_16 = SF_FORMAT_DWVW_16
    DWVW_24 = SF_FORMAT_DWVW_24
    DWVW_N = SF_FORMAT_DWVW_N
    DPCM_8 = SF_FORMAT_DPCM_8
    DPCM_16 = SF_FORMAT_DPCM_16
    VORBIS = SF_FORMAT_VORBIS


cdef class SndFile(object):
    cdef readonly str path
    cdef object _fp
    cdef SNDFILE* _sf
    cdef SF_INFO _sfinfo

    def __init__(self, path):
        self.path = path
        self._sf = NULL
        self._sfinfo.format = 0

        self._fp = open(path, 'rb')
        self._sf = sf_open_fd(self._fp.fileno(), SFM_READ, &self._sfinfo, False)
        if self._sf == NULL:
            raise Error(bytes(sf_strerror(NULL)).decode('utf-8'))

    def __dealloc__(self):
        if self._sf != NULL:
            sf_close(self._sf)
            self._sf = NULL

        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _raise_error(self):
        raise Error(bytes(sf_strerror(self._sf)).decode('utf-8'))

    def close(self):
        if self._sf != NULL:
            sf_close(self._sf)
            self._sf = NULL

    @property
    def num_samples(self):
        return self._sfinfo.frames

    @property
    def sample_rate(self):
        return self._sfinfo.samplerate

    @property
    def num_channels(self):
        return self._sfinfo.channels

    @property
    def file_format(self):
        return FileFormat(self._sfinfo.format & SF_FORMAT_TYPEMASK)

    @property
    def encoding(self):
        return Encoding(self._sfinfo.format & SF_FORMAT_SUBMASK)

    def get_samples(self):
        if sf_seek(self._sf, 0, SEEK_SET) == -1:
            self._raise_error()

        num_items = self.num_samples * self.num_channels
        cdef numpy.ndarray[float, ndim=2, mode="c"] buf = numpy.ndarray(
            shape=(self.num_samples, self.num_channels), dtype=numpy.float32, order='C')
        items_read = sf_read_float(self._sf, &buf[0,0], num_items)
        if items_read != num_items:
            raise Error("Failed to read all items (%d < %d)" % (items_read, num_items))
        return buf
